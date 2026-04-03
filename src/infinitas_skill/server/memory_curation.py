from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from infinitas_skill.memory.policy import resolve_memory_policy
from server.models import AuditEvent
from server.modules.audit.service import append_audit_event

CURATION_ACTIONS = {"plan", "archive", "prune"}
CURATION_RECORDED_STATUSES = {"archived", "pruned"}


def _payload(event: AuditEvent) -> dict[str, Any]:
    try:
        payload = json.loads(event.payload_json or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _fingerprint(lifecycle_event: str, payload: dict[str, Any]) -> str:
    safe_payload = payload if isinstance(payload, dict) else {}
    return json.dumps(
        {
            "lifecycle_event": lifecycle_event,
            "payload": safe_payload,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _normalized_limit(limit: int, default: int) -> int:
    return limit if isinstance(limit, int) and limit > 0 else default


def _normalized_action(action: str) -> str:
    normalized = str(action or "").strip().lower() or "plan"
    return normalized if normalized in CURATION_ACTIONS else "plan"


def _memory_writeback_events(session: Session, *, limit: int) -> list[AuditEvent]:
    return session.scalars(
        select(AuditEvent)
        .where(AuditEvent.aggregate_type == "memory_writeback")
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    ).all()


def _curated_candidate_refs(session: Session) -> set[str]:
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.aggregate_type == "memory_curation")
    ).all()
    curated: set[str] = set()
    for event in events:
        if event.event_type not in {"memory.curation.archived", "memory.curation.pruned"}:
            continue
        curated.add(str(event.aggregate_id))
    return curated


def _candidate_ref(event: AuditEvent) -> str:
    return f"memory_writeback:{int(event.id)}"


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, datetime, int]:
    reasons = candidate.get("reasons") if isinstance(candidate.get("reasons"), list) else []
    duplicate_priority = 0 if "duplicate" in reasons else 1
    occurred_at = _parse_datetime(candidate.get("occurred_at")) or datetime.max.replace(
        tzinfo=timezone.utc
    )
    return (
        duplicate_priority,
        occurred_at,
        int(candidate.get("event_id") or 0),
    )


def _append_curation_audit_event(
    session: Session,
    *,
    candidate: dict[str, Any],
    action: str,
    status: str,
    actor_ref: str,
    error: str | None = None,
) -> AuditEvent:
    payload = {
        "action": action,
        "status": status,
        "candidate_event_id": candidate.get("event_id"),
        "source_aggregate_id": candidate.get("aggregate_id"),
        "memory_id": candidate.get("memory_id"),
        "lifecycle_event": candidate.get("lifecycle_event"),
        "backend": candidate.get("backend"),
        "occurred_at": candidate.get("occurred_at"),
        "reasons": list(candidate.get("reasons") or []),
    }
    if error:
        payload["error"] = error
    return append_audit_event(
        session,
        aggregate_type="memory_curation",
        aggregate_id=str(candidate.get("candidate_ref") or ""),
        event_type=f"memory.curation.{status}",
        actor_ref=actor_ref,
        payload=payload,
    )


def _collect_curation_state(
    session: Session,
    *,
    limit: int = 50,
    now: str | datetime | None = None,
    include_curated: bool = False,
) -> dict[str, Any]:
    normalized_limit = _normalized_limit(limit, 50)
    resolved_now = _parse_datetime(now) or datetime.now(timezone.utc)
    events = _memory_writeback_events(session, limit=normalized_limit)
    curated_refs = set() if include_curated else _curated_candidate_refs(session)

    duplicate_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    expired_events: list[dict[str, Any]] = []
    expired_counts: Counter[str] = Counter()
    candidates_by_ref: dict[str, dict[str, Any]] = {}

    for event in events:
        payload = _payload(event)
        status = str(payload.get("status") or "").strip().lower()
        lifecycle_event = str(payload.get("lifecycle_event") or "").strip()
        backend = str(payload.get("backend") or "").strip()
        memory_id = str(payload.get("memory_id") or "").strip() or None
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
        candidate = {
            "event_id": int(event.id),
            "candidate_ref": _candidate_ref(event),
            "aggregate_id": str(event.aggregate_id),
            "memory_id": memory_id,
            "lifecycle_event": lifecycle_event,
            "backend": backend,
            "occurred_at": str(event.occurred_at),
            "payload": event_payload,
            "reasons": [],
        }

        if status == "stored" and lifecycle_event:
            duplicate_groups[_fingerprint(lifecycle_event, event_payload)].append(candidate)
            occurred_at = _parse_datetime(event.occurred_at)
            policy = resolve_memory_policy(lifecycle_event)
            if (
                occurred_at is not None
                and (resolved_now - occurred_at).total_seconds() > policy.ttl_seconds
            ):
                expired_events.append(
                    {
                        "id": int(event.id),
                        "lifecycle_event": lifecycle_event,
                        "backend": backend,
                        "occurred_at": str(event.occurred_at),
                    }
                )
                expired_counts[lifecycle_event] += 1
                if candidate["candidate_ref"] not in curated_refs:
                    current = candidates_by_ref.setdefault(
                        candidate["candidate_ref"],
                        dict(candidate),
                    )
                    current["reasons"] = sorted(set(current.get("reasons", [])) | {"expired"})

    top_duplicate_groups = []
    for items in duplicate_groups.values():
        if len(items) <= 1:
            continue
        sample = items[0]
        top_duplicate_groups.append(
            {
                "lifecycle_event": sample["lifecycle_event"],
                "count": len(items),
                "backend_names": sorted(
                    {
                        item["backend"]
                        for item in items
                        if isinstance(item.get("backend"), str) and item["backend"]
                    }
                ),
                "sample_payload": sample["payload"],
            }
        )
        for duplicate in items[1:]:
            if duplicate["candidate_ref"] in curated_refs:
                continue
            current = candidates_by_ref.setdefault(duplicate["candidate_ref"], dict(duplicate))
            current["reasons"] = sorted(set(current.get("reasons", [])) | {"duplicate"})
    top_duplicate_groups.sort(key=lambda item: (-item["count"], item["lifecycle_event"]))

    top_expired_lifecycle_events = [
        {"lifecycle_event": lifecycle_event, "count": count}
        for lifecycle_event, count in expired_counts.most_common(5)
    ]
    candidates = sorted(candidates_by_ref.values(), key=_candidate_sort_key)

    return {
        "ok": True,
        "limit": normalized_limit,
        "candidate_counts": {
            "duplicate_groups": len(top_duplicate_groups),
            "expired_by_policy": len(expired_events),
            "actionable_candidates": len(candidates),
        },
        "top_duplicate_groups": top_duplicate_groups[:5],
        "top_expired_lifecycle_events": top_expired_lifecycle_events,
        "recent_expired_candidates": expired_events[:5],
        "candidates": candidates,
    }


def summarize_memory_curation_plan(
    session: Session,
    *,
    limit: int = 50,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    summary = _collect_curation_state(session, limit=limit, now=now)
    summary["action"] = "plan"
    summary["apply"] = False
    summary["execution"] = {
        "selected_candidates": 0,
        "pruned": 0,
        "archived": 0,
        "skipped": 0,
        "failed": 0,
    }
    return summary


def execute_memory_curation(
    session: Session,
    *,
    action: str = "plan",
    apply: bool = False,
    provider: Any | None = None,
    limit: int = 50,
    max_actions: int = 20,
    now: str | datetime | None = None,
    actor_ref: str = "system:memory-curation",
) -> dict[str, Any]:
    resolved_action = _normalized_action(action)
    summary = _collect_curation_state(session, limit=limit, now=now)
    selected_candidates = summary["candidates"][: _normalized_limit(max_actions, 20)]
    execution = {
        "selected_candidates": len(selected_candidates),
        "pruned": 0,
        "archived": 0,
        "skipped": 0,
        "failed": 0,
    }
    summary["action"] = resolved_action
    summary["apply"] = bool(apply and resolved_action != "plan")
    summary["execution"] = execution

    if resolved_action == "plan" or not summary["apply"]:
        return summary

    for candidate in selected_candidates:
        if resolved_action == "archive":
            _append_curation_audit_event(
                session,
                candidate=candidate,
                action=resolved_action,
                status="archived",
                actor_ref=actor_ref,
            )
            execution["archived"] += 1
            continue

        memory_id = candidate.get("memory_id")
        if not isinstance(memory_id, str) or not memory_id.strip():
            _append_curation_audit_event(
                session,
                candidate=candidate,
                action=resolved_action,
                status="skipped",
                actor_ref=actor_ref,
                error="memory_id_required",
            )
            execution["skipped"] += 1
            continue
        try:
            delete_result = provider.delete(memory_id=memory_id)
        except Exception:
            _append_curation_audit_event(
                session,
                candidate=candidate,
                action=resolved_action,
                status="failed",
                actor_ref=actor_ref,
                error="provider_delete_failed",
            )
            execution["failed"] += 1
            continue
        status = str(getattr(delete_result, "status", "") or "").strip().lower()
        if status == "deleted":
            _append_curation_audit_event(
                session,
                candidate=candidate,
                action=resolved_action,
                status="pruned",
                actor_ref=actor_ref,
            )
            execution["pruned"] += 1
            continue
        _append_curation_audit_event(
            session,
            candidate=candidate,
            action=resolved_action,
            status="skipped",
            actor_ref=actor_ref,
            error="provider_delete_skipped",
        )
        execution["skipped"] += 1

    return summary


__all__ = ["execute_memory_curation", "summarize_memory_curation_plan"]
