from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.auth_guards import require_user_role
from server.db import get_db
from server.models import AuditEvent, Credential
from server.modules.access.authn import AccessContext
from server.modules.access.models import AccessGrant
from server.modules.audit.read_model import activity_query, normalize_event

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


def _assert_token_owner(
    db: Session, token_id: int, principal_id: int, is_maintainer: bool
) -> None:
    if is_maintainer:
        return
    credential = db.get(Credential, token_id)
    if credential is None or credential.principal_id != principal_id:
        raise HTTPException(status_code=403, detail="token access denied")


def _assert_share_owner(
    db: Session, share_id: int, principal_id: int, is_maintainer: bool
) -> None:
    if is_maintainer:
        return
    grant = db.get(AccessGrant, share_id)
    if grant is None or grant.grant_type != "link" or grant.created_by_principal_id != principal_id:
        raise HTTPException(status_code=403, detail="share link access denied")


@router.get("/")
def list_activity(
    limit: int = 100,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    require_user_role(context)
    capped_limit = max(1, min(int(limit or 100), 500))
    events = db.scalars(activity_query().limit(capped_limit)).all()
    items = [normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}


@router.get("/tokens/{token_id}/activity")
def token_activity(
    token_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    require_user_role(context)
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
    items = [normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}


@router.get("/share-links/{share_id}/activity")
def share_link_activity(
    share_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    require_user_role(context)
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
    items = [normalize_event(db, event) for event in events]
    return {"items": items, "total": len(items)}
