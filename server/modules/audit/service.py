from __future__ import annotations

import json
from typing import Any, Mapping

from sqlalchemy.orm import Session

from server.modules.audit.models import AuditEvent


def append_audit_event(
    db: Session,
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    actor_ref: str = "",
    payload: Mapping[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        aggregate_type=str(aggregate_type or "").strip(),
        aggregate_id=str(aggregate_id or "").strip(),
        event_type=str(event_type or "").strip(),
        actor_ref=str(actor_ref or "").strip(),
        payload_json=json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
    )
    db.add(event)
    db.flush()
    return event
