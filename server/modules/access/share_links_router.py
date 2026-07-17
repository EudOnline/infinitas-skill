from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import server.modules.access.share_links as share_service
from server.db import get_db, session_scope
from server.modules.access.authn import AccessContext
from server.modules.access.schemas import ShareLinkListView, ShareLinkView
from server.modules.identity.auth import get_current_access_context
from server.modules.identity.guards import require_actor_ref as _require_actor
from server.rate_limit import DBRateLimiter, resolve_rate_limit_key

router = APIRouter(prefix="/api/v1/share-links", tags=["share-links"])

_SHARE_RATE_MAX = 20
_SHARE_RATE_WINDOW = 60  # seconds


class ShareLinkCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    password: str | None = Field(default=None, max_length=200)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
    max_uses: int | None = Field(default=None, ge=1, le=100000)


class ShareLinkResolveRequest(BaseModel):
    password: str | None = Field(default=None, max_length=200)
    secret: str | None = Field(default=None, min_length=1, max_length=512)


def _translate_error(exc: share_service.ShareLinkError) -> HTTPException:
    if isinstance(exc, share_service.ShareLinkNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, share_service.ShareLinkForbiddenError):
        return HTTPException(status_code=403, detail=str(exc))
    detail = str(exc)
    if detail in {"revoked", "expired", "exhausted"}:
        return HTTPException(status_code=410, detail=detail)
    return HTTPException(status_code=409, detail=detail)


def _enforce_share_rate_limit(request: Request, *, operation: str, share_id: int | None) -> None:
    client_key = resolve_rate_limit_key(request)
    object_key = f":{share_id}" if share_id is not None else ""
    rate_limit_key = f"share-{operation}{object_key}:{client_key}"
    with session_scope() as rate_limit_db:
        allowed = DBRateLimiter(rate_limit_db).consume(
            rate_limit_key,
            max_attempts=_SHARE_RATE_MAX,
            window_seconds=_SHARE_RATE_WINDOW,
        )
    if allowed:
        return
    raise HTTPException(
        status_code=429,
        detail=f"Too many share {operation} requests. Please try again later.",
        headers={"Retry-After": str(_SHARE_RATE_WINDOW)},
    )


@router.post(
    "/releases/{release_id}/share-links",
    response_model=ShareLinkView,
    status_code=status.HTTP_201_CREATED,
)
def create_share_link(
    release_id: int,
    payload: ShareLinkCreateRequest,
    request: Request,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _enforce_share_rate_limit(request, operation="create", share_id=None)
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
    base_url = str(request.base_url).rstrip("/")
    share["install_url"] = f"{base_url}{share['install_path']}"
    share["resolve_path"] = f"/api/v1/share-links/{share['id']}/resolve"
    share["resolve_url"] = f"{base_url}{share['resolve_path']}"
    return share


@router.get("/releases/{release_id}/share-links", response_model=ShareLinkListView)
def list_share_links(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    actor = _require_actor(context)
    try:
        items = share_service.list_share_links(db, release_id=release_id, actor=actor)
    except share_service.ShareLinkError as exc:
        raise _translate_error(exc) from exc
    return {"items": items, "total": len(items)}


@router.post("/{share_id}/revoke", response_model=ShareLinkView)
def revoke_share_link(
    share_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    actor = _require_actor(context)
    try:
        share = share_service.revoke_share_link(db, share_id=share_id, actor=actor)
    except share_service.ShareLinkError as exc:
        raise _translate_error(exc) from exc
    return share


@router.post("/{share_id}/resolve", response_model=ShareLinkView)
def resolve_share_link(
    share_id: int,
    payload: ShareLinkResolveRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _enforce_share_rate_limit(request, operation="resolve", share_id=share_id)
    try:
        share = share_service.resolve_share_link(
            db,
            share_id=share_id,
            password=payload.password,
            secret=payload.secret,
        )
    except share_service.ShareLinkError as exc:
        raise _translate_error(exc) from exc
    base_url = str(request.base_url).rstrip("/")
    share["install_url"] = f"{base_url}{share['install_path']}"
    return share
