from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.models import AuditEvent, RegistryObject, Release
from server.modules.access.authn import AccessContext

router = APIRouter(tags=["activity"])


def _require_actor(context: AccessContext) -> None:
    if context.user is None:
        raise HTTPException(status_code=403, detail="user session required")
    if context.user.role not in {"maintainer", "contributor"}:
        raise HTTPException(status_code=403, detail="insufficient role")


def _json_payload(event: AuditEvent) -> dict[str, Any]:
    try:
        payload = json.loads(event.payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _object_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any] | None:
    object_id = payload.get("object_id")
    if not object_id:
        return None
    registry_object = db.get(RegistryObject, int(object_id))
    if registry_object is None:
        return {"id": int(object_id), "name": None, "kind": None}
    return {
        "id": registry_object.id,
        "name": registry_object.display_name,
        "kind": registry_object.kind,
    }


def _release_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any] | None:
    release_id = payload.get("release_id")
    if not release_id:
        return None
    release = db.get(Release, int(release_id))
    if release is None:
        return {"id": int(release_id), "state": None}
    return {"id": release.id, "state": release.state}


def _normalize_event(db: Session, event: AuditEvent) -> dict[str, Any]:
    payload = _json_payload(event)
    return {
        "id": event.id,
        "actor": event.actor_ref or "system",
        "action": event.event_type,
        "object": _object_payload(db, payload),
        "release": _release_payload(db, payload),
        "outcome": payload.get("outcome") or "success",
        "timestamp": event.occurred_at.isoformat().replace("+00:00", "Z"),
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "detail": payload,
    }


def _activity_query():
    return select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())


@router.get("/api/activity")
def list_activity(
    limit: int = 100,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    _require_actor(context)
    capped_limit = max(1, min(int(limit or 100), 500))
    events = db.scalars(_activity_query().limit(capped_limit)).all()
    items = [_normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}


@router.get("/api/tokens/{token_id}/activity")
def token_activity(
    token_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    _require_actor(context)
    events = db.scalars(
        _activity_query()
        .where(AuditEvent.aggregate_type == "token")
        .where(AuditEvent.aggregate_id == str(token_id))
    ).all()
    items = [_normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}


@router.get("/api/share-links/{share_id}/activity")
def share_link_activity(
    share_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    _require_actor(context)
    events = db.scalars(
        _activity_query()
        .where(AuditEvent.aggregate_type == "share_link")
        .where(AuditEvent.aggregate_id == str(share_id))
    ).all()
    items = [_normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}
