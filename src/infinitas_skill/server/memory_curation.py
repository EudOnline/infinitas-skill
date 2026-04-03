from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from infinitas_skill.memory.policy import resolve_memory_policy
from server.models import AuditEvent


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


def summarize_memory_curation_plan(
    session: Session,
    *,
    limit: int = 50,
    now: str | datetime | None = None,
) -> dict[str, Any]:
    normalized_limit = limit if isinstance(limit, int) and limit > 0 else 50
    resolved_now = _parse_datetime(now) or datetime.now(timezone.utc)
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.aggregate_type == "memory_writeback")
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(normalized_limit)
    ).all()

    duplicate_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    expired_events: list[dict[str, Any]] = []
    expired_counts: Counter[str] = Counter()

    for event in events:
        payload = _payload(event)
        status = str(payload.get("status") or "").strip().lower()
        lifecycle_event = str(payload.get("lifecycle_event") or "").strip()
        backend = str(payload.get("backend") or "").strip()
        event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}

        if status == "stored" and lifecycle_event:
            duplicate_groups[_fingerprint(lifecycle_event, event_payload)].append(
                {
                    "lifecycle_event": lifecycle_event,
                    "backend": backend,
                    "payload": event_payload,
                }
            )
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
    top_duplicate_groups.sort(
        key=lambda item: (-item["count"], item["lifecycle_event"])
    )

    top_expired_lifecycle_events = [
        {"lifecycle_event": lifecycle_event, "count": count}
        for lifecycle_event, count in expired_counts.most_common(5)
    ]

    return {
        "ok": True,
        "limit": normalized_limit,
        "candidate_counts": {
            "duplicate_groups": len(top_duplicate_groups),
            "expired_by_policy": len(expired_events),
        },
        "top_duplicate_groups": top_duplicate_groups[:5],
        "top_expired_lifecycle_events": top_expired_lifecycle_events,
        "recent_expired_candidates": expired_events[:5],
    }


__all__ = ["summarize_memory_curation_plan"]
