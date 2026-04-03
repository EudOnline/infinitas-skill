from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from infinitas_skill.server.memory_baselines import summarize_memory_baselines
from infinitas_skill.server.memory_health import summarize_memory_writeback
from server.models import AuditEvent, Job


def _payload(raw: str | None) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _curation_status(event: AuditEvent) -> str:
    event_type = str(event.event_type or "").strip().lower()
    if event_type.startswith("memory.curation."):
        return event_type.removeprefix("memory.curation.")
    return "unknown"


def _retrieval_status(payload: dict[str, Any]) -> str:
    memory = payload.get("memory")
    if not isinstance(memory, dict):
        return "unknown"
    status = str(memory.get("status") or "").strip().lower()
    return status or "unknown"


def _retrieval_effect(payload: dict[str, Any]) -> str:
    effect = str(payload.get("effect") or "").strip().lower()
    return effect or "unknown"


def summarize_memory_observability(
    session: Session,
    *,
    limit: int = 20,
    job_limit: int = 10,
    now: str | None = None,
    window_hours: int = 24,
) -> dict[str, Any]:
    normalized_limit = limit if isinstance(limit, int) and limit > 0 else 20
    normalized_job_limit = job_limit if isinstance(job_limit, int) and job_limit > 0 else 10
    writeback = summarize_memory_writeback(session, limit=normalized_limit)
    baselines = summarize_memory_baselines(session, now=now, window_hours=window_hours)

    curation_events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.aggregate_type == "memory_curation")
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(normalized_limit)
    ).all()
    curation_status_counts: Counter[str] = Counter()
    curation_action_counts: Counter[str] = Counter()
    recent_curation = []
    for event in curation_events:
        payload = _payload(event.payload_json)
        status = _curation_status(event)
        action = str(payload.get("action") or "").strip().lower()
        curation_status_counts[status] += 1
        if action:
            curation_action_counts[action] += 1
        recent_curation.append(
            {
                "id": int(event.id),
                "status": status,
                "action": action,
                "occurred_at": str(event.occurred_at),
                "candidate_ref": str(event.aggregate_id or ""),
            }
        )

    jobs = session.scalars(
        select(Job)
        .where(Job.kind == "memory_curation")
        .order_by(Job.created_at.desc(), Job.id.desc())
        .limit(normalized_job_limit)
    ).all()
    job_status_counts: Counter[str] = Counter()
    recent_jobs = []
    for job in jobs:
        payload = _payload(job.payload_json)
        status = str(job.status or "").strip().lower() or "unknown"
        job_status_counts[status] += 1
        recent_jobs.append(
            {
                "id": int(job.id),
                "status": status,
                "kind": str(job.kind or ""),
                "note": str(job.note or ""),
                "created_at": str(job.created_at),
                "payload": payload,
            }
        )

    retrieval_events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.aggregate_type == "memory_retrieval")
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(normalized_limit)
    ).all()
    retrieval_status_counts: Counter[str] = Counter()
    retrieval_operation_counts: Counter[str] = Counter()
    retrieval_effect_counts: Counter[str] = Counter()
    recent_retrieval = []
    for event in retrieval_events:
        payload = _payload(event.payload_json)
        status = _retrieval_status(payload)
        operation = str(payload.get("operation") or "").strip().lower() or "unknown"
        effect = _retrieval_effect(payload)
        retrieval_status_counts[status] += 1
        retrieval_operation_counts[operation] += 1
        retrieval_effect_counts[effect] += 1
        recent_retrieval.append(
            {
                "id": int(event.id),
                "operation": operation,
                "status": status,
                "effect": effect,
                "actor_ref": str(event.actor_ref or ""),
                "occurred_at": str(event.occurred_at),
                "aggregate_id": str(event.aggregate_id or ""),
            }
        )

    return {
        "ok": True,
        "limit": normalized_limit,
        "job_limit": normalized_job_limit,
        "writeback": writeback,
        "curation": {
            "status_counts": dict(curation_status_counts),
            "action_counts": dict(curation_action_counts),
            "recent": recent_curation[:5],
        },
        "jobs": {
            "status_counts": dict(job_status_counts),
            "recent": recent_jobs[:5],
        },
        "retrieval": {
            "status_counts": dict(retrieval_status_counts),
            "operation_counts": dict(retrieval_operation_counts),
            "effect_counts": dict(retrieval_effect_counts),
            "recent": recent_retrieval[:5],
        },
        "baselines": baselines,
    }


__all__ = ["summarize_memory_observability"]
