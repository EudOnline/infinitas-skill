from __future__ import annotations

import json
from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import AuditEvent


def _payload(event: AuditEvent) -> dict[str, Any]:
    try:
        payload = json.loads(event.payload_json or "{}")
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def summarize_memory_writeback(session: Session, *, limit: int = 20) -> dict[str, Any]:
    normalized_limit = limit if isinstance(limit, int) and limit > 0 else 20
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.aggregate_type == "memory_writeback")
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(normalized_limit)
    ).all()

    status_counts: Counter[str] = Counter()
    failed_lifecycle_counts: Counter[str] = Counter()
    backend_names: set[str] = set()
    recent_failures = []

    for event in events:
        payload = _payload(event)
        status = str(payload.get("status") or "").strip().lower()
        lifecycle_event = str(payload.get("lifecycle_event") or "").strip()
        backend = str(payload.get("backend") or "").strip()

        if status:
            status_counts[status] += 1
        if backend:
            backend_names.add(backend)
        if status == "failed":
            if lifecycle_event:
                failed_lifecycle_counts[lifecycle_event] += 1
            recent_failures.append(
                {
                    "id": int(event.id),
                    "lifecycle_event": lifecycle_event,
                    "backend": backend,
                    "occurred_at": str(event.occurred_at),
                }
            )

    top_failed = [
        {"lifecycle_event": lifecycle_event, "count": count}
        for lifecycle_event, count in failed_lifecycle_counts.most_common(5)
    ]
    return {
        "ok": True,
        "limit": normalized_limit,
        "writeback_status_counts": dict(status_counts),
        "backend_names": sorted(backend_names),
        "top_failed_lifecycle_events": top_failed,
        "recent_failures": recent_failures[:5],
    }


__all__ = ["summarize_memory_writeback"]
