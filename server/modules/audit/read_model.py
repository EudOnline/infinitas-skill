from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from server.models import AuditEvent


def json_payload(event: AuditEvent) -> dict[str, Any]:
    try:
        payload = json.loads(event.payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def activity_query():
    return select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
