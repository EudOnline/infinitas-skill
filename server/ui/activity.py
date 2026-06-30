from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from server.models import AuditEvent
from server.modules.audit.read_model import json_payload
from server.modules.shared.formatting import iso_format
from server.ui.formatting import humanize_identifier, humanize_timestamp
from server.ui.queries import get_audit_events, get_release_label, get_skill_name


def _iso_stamp(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return iso_format(value)
    return str(value)


def _event_category(event: AuditEvent, payload: dict[str, Any]) -> str:
    event_type = str(event.event_type or "")
    aggregate_type = str(event.aggregate_type or "")
    if aggregate_type == "share_link" or event_type.startswith("share_link."):
        return "share"
    if aggregate_type == "token" or event_type.startswith("token."):
        return "token"
    if aggregate_type == "exposure" or event_type.startswith("task.exposure."):
        return "visibility"
    explicit_type = str(payload.get("event_type") or payload.get("category") or "").strip()
    return explicit_type or aggregate_type or "audit"


def _actor_label(actor_ref: str | None) -> str | None:
    text = str(actor_ref or "").strip()
    if not text:
        return None
    return text.removeprefix("principal:")


def _object_name(db: Session, payload: dict[str, Any]) -> str | None:
    """Get object name from payload.

    Delegates to ui_service layer for database access.
    """
    explicit = payload.get("object_name") or payload.get("name")
    if explicit:
        return str(explicit)
    object_id = payload.get("object_id")
    if object_id is None:
        return None
    return get_skill_name(db, int(object_id)) or str(object_id)


def _release_label(db: Session, payload: dict[str, Any]) -> str | None:
    """Get release label from payload.

    Delegates to ui_service layer for database access.
    """
    release_id = payload.get("release_id")
    if release_id is None:
        return None
    return get_release_label(db, int(release_id))


def _title_for_event(event: AuditEvent, payload: dict[str, Any]) -> str:
    if payload.get("title"):
        return str(payload["title"])
    event_type = str(event.event_type or "").strip()
    if event_type == "share_link.created":
        return "Share link issued"
    if event_type == "share_link.revoked":
        return "Share link revoked"
    if event_type == "share_link.resolved":
        return "Share link used"
    if event_type == "token.created":
        token_type = str(payload.get("token_type") or "agent")
        return f"{token_type} token issued"
    if event_type == "token.revoked":
        token_type = str(payload.get("token_type") or "reader")
        return f"{token_type} token revoked"
    if event_type.startswith("task.exposure."):
        return humanize_identifier(event_type.removeprefix("task."))
    return humanize_identifier(event_type or event.aggregate_type or "audit event")


def _description_for_event(
    db: Session,
    event: AuditEvent,
    payload: dict[str, Any],
    *,
    object_name: str | None,
) -> str:
    if payload.get("description"):
        return str(payload["description"])
    release_label = _release_label(db, payload)
    event_type = str(event.event_type or "").strip()
    if event_type.startswith("share_link."):
        target = object_name or "release"
        return f"{target} share event for {release_label or 'release'}."
    if event_type.startswith("token."):
        target = object_name or "object"
        token_type = str(payload.get("token_type") or "agent")
        return f"{token_type} token event for {target}."
    if event_type.startswith("task.exposure."):
        audience = payload.get("audience_type")
        state = payload.get("state")
        target = object_name or release_label or "release"
        suffix = f" is {state}" if state else ""
        audience_text = f" for {audience} access" if audience else ""
        return f"{target}{suffix}{audience_text}."
    return str(payload.get("detail") or event.aggregate_type or event.event_type or "audit")


_CATEGORY_ICONS: dict[str, str] = {
    "share": "🔗",
    "token": "🔑",
    "visibility": "👁️",
    "audit": "📋",
}


def normalize_audit_event_for_ui(db: Session, event: AuditEvent) -> dict[str, Any]:
    payload = json_payload(event)
    object_name = _object_name(db, payload)
    category = _event_category(event, payload)
    title = _title_for_event(event, payload)
    sort_at = event.occurred_at
    if sort_at is None:
        sort_at = datetime.min.replace(tzinfo=timezone.utc)
    return {
        "id": event.id,
        "event_type": category,
        "title": title,
        "event": title,
        "description": _description_for_event(
            db,
            event,
            payload,
            object_name=object_name,
        ),
        "object_name": object_name,
        "actor": _actor_label(event.actor_ref),
        "timestamp": humanize_timestamp(_iso_stamp(event.occurred_at)),
        "icon": _CATEGORY_ICONS.get(category, "📝"),
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "detail": payload,
        "_sort_at": sort_at,
    }


def list_activity_rows(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    """List activity rows for the UI.

    Delegates to ui_service layer for database access.
    """
    capped_limit = max(1, min(int(limit or 100), 500))
    events = get_audit_events(db, limit=capped_limit)
    return [normalize_audit_event_for_ui(db, event) for event in events]
