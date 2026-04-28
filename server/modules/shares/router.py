from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.shares import service as share_service

router = APIRouter(tags=["share-links"])


class ShareLinkCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, max_length=200)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
    max_uses: int | None = Field(default=None, ge=1, le=100000)


class ShareLinkResolveRequest(BaseModel):
    password: str | None = Field(default=None, max_length=200)


def _require_actor(context: AccessContext) -> share_service.ActorRef:
    if context.user is None or context.principal is None:
        raise HTTPException(status_code=403, detail="user session required")
    if context.user.role not in {"maintainer", "contributor"}:
        raise HTTPException(status_code=403, detail="insufficient role")
    return share_service.ActorRef(
        principal=context.principal,
        is_maintainer=context.user.role == "maintainer",
    )


def _translate_error(exc: share_service.ShareLinkError) -> HTTPException:
    if isinstance(exc, share_service.ShareLinkNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, share_service.ShareLinkForbiddenError):
        return HTTPException(status_code=403, detail=str(exc))
    detail = str(exc)
    if detail in {"revoked", "expired", "exhausted"}:
        return HTTPException(status_code=410, detail=detail)
    return HTTPException(status_code=409, detail=detail)


@router.post("/api/releases/{release_id}/share-links", status_code=status.HTTP_201_CREATED)
def create_share_link(
    release_id: int,
    payload: ShareLinkCreateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_actor(context)
    try:
        share = share_service.create_share_link(
            db,
            release_id=release_id,
            name=payload.name,
            password=payload.password,
            expires_in_days=payload.expires_in_days,
            max_uses=payload.max_uses,
            actor=actor,
        )
    except share_service.ShareLinkError as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return share


@router.get("/api/releases/{release_id}/share-links")
def list_share_links(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_actor(context)
    try:
        items = share_service.list_share_links(db, release_id=release_id, actor=actor)
    except share_service.ShareLinkError as exc:
        raise _translate_error(exc) from exc
    return {"items": items, "total": len(items)}


@router.post("/api/share-links/{share_id}/revoke")
def revoke_share_link(
    share_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_actor(context)
    try:
        share = share_service.revoke_share_link(db, share_id=share_id, actor=actor)
    except share_service.ShareLinkError as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return share


@router.post("/api/share-links/{share_id}/resolve")
def resolve_share_link(
    share_id: int,
    payload: ShareLinkResolveRequest,
    db: Session = Depends(get_db),
):
    try:
        share = share_service.resolve_share_link(
            db,
            share_id=share_id,
            password=payload.password,
        )
    except share_service.ShareLinkError as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return share
