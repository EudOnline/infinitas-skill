from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.models import AuditEvent, Credential, Release, Skill
from server.modules.access.authn import AccessContext
from server.modules.access.models import AccessGrant
from server.modules.audit.read_model import activity_query, json_payload

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


def _require_actor(context: AccessContext) -> None:
    if context.user is None:
        raise HTTPException(status_code=403, detail="user session required")
    if context.user.role not in {"maintainer", "contributor"}:
        raise HTTPException(status_code=403, detail="insufficient role")


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


def _normalize_event(db: Session, event: AuditEvent) -> dict[str, Any]:
    payload = json_payload(event)
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


@router.get("/")
def list_activity(
    limit: int = 100,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    _require_actor(context)
    capped_limit = max(1, min(int(limit or 100), 500))
    events = db.scalars(activity_query().limit(capped_limit)).all()
    items = [_normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}


def _assert_token_owner(
    db: Session, token_id: int, principal_id: int, is_maintainer: bool
) -> None:
    if is_maintainer:
        return
    credential = db.get(Credential, token_id)
    if credential is None or credential.principal_id != principal_id:
        raise HTTPException(status_code=403, detail="token access denied")


@router.get("/tokens/{token_id}/activity")
def token_activity(
    token_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    _require_actor(context)
    _assert_token_owner(
        db,
        token_id,
        context.principal.id if context.principal else 0,
        context.user.role == "maintainer" if context.user else False,
    )
    events = db.scalars(
        activity_query()
        .where(AuditEvent.aggregate_type == "token")
        .where(AuditEvent.aggregate_id == str(token_id))
    ).all()
    items = [_normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}


def _assert_share_owner(
    db: Session, share_id: int, principal_id: int, is_maintainer: bool
) -> None:
    if is_maintainer:
        return
    grant = db.get(AccessGrant, share_id)
    if grant is None or grant.grant_type != "link" or grant.created_by_principal_id != principal_id:
        raise HTTPException(status_code=403, detail="share link access denied")


@router.get("/share-links/{share_id}/activity")
def share_link_activity(
    share_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    _require_actor(context)
    _assert_share_owner(
        db,
        share_id,
        context.principal.id if context.principal else 0,
        context.user.role == "maintainer" if context.user else False,
    )
    events = db.scalars(
        activity_query()
        .where(AuditEvent.aggregate_type == "share_link")
        .where(AuditEvent.aggregate_id == str(share_id))
    ).all()
    items = [_normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}
