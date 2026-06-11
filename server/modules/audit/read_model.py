from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import AuditEvent, Release, Skill
from server.modules.shared.formatting import iso_format


def json_payload(event: AuditEvent) -> dict[str, Any]:
    try:
        payload = json.loads(event.payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def activity_query():
    return select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())


def _object_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any] | None:
    object_id = payload.get("object_id")
    if not object_id:
        return None
    skill = db.get(Skill, int(object_id))
    if skill is None:
        return {"id": int(object_id), "name": None, "kind": None}
    return {
        "id": skill.id,
        "name": skill.display_name,
        "kind": "skill",
    }


def _release_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any] | None:
    release_id = payload.get("release_id")
    if not release_id:
        return None
    release = db.get(Release, int(release_id))
    if release is None:
        return {"id": int(release_id), "state": None}
    return {"id": release.id, "state": release.state}


def normalize_event(db: Session, event: AuditEvent) -> dict[str, Any]:
    """Enrich an audit event with resolved object/release references."""
    payload = json_payload(event)
    return {
        "id": event.id,
        "actor": event.actor_ref or "system",
        "action": event.event_type,
        "object": _object_payload(db, payload),
        "release": _release_payload(db, payload),
        "outcome": payload.get("outcome") or "success",
        "timestamp": iso_format(event.occurred_at),
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "detail": payload,
    }
