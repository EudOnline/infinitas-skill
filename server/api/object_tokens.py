from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.auth_guards import require_actor_ref as _require_actor
from server.db import get_db
from server.modules.access import token_service
from server.modules.access.authn import AccessContext
from server.rate_limit import get_rate_limiter, resolve_client_ip

router = APIRouter(prefix="/api/v1/object-tokens", tags=["object-tokens"])

_TOKEN_RATE_MAX = 20
_TOKEN_RATE_WINDOW = 60  # seconds


class ObjectTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["reader", "publisher"] = "reader"
    scope_type: Literal["object", "release"] = "release"
    scope_id: int = Field(gt=0)
    issued_for: str | None = Field(default=None, max_length=200)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)


def _translate_error(exc: token_service.TokenServiceError) -> HTTPException:
    if isinstance(exc, token_service.TokenNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, token_service.TokenForbiddenError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/objects/{object_id}/tokens", status_code=status.HTTP_201_CREATED)
def create_object_token(
    object_id: int,
    payload: ObjectTokenCreateRequest,
    request: Request,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    client_ip = resolve_client_ip(request)
    limiter = get_rate_limiter()
    if not limiter.check(
        client_ip, max_attempts=_TOKEN_RATE_MAX, window_seconds=_TOKEN_RATE_WINDOW
    ):
        raise HTTPException(
            status_code=429,
            detail="Too many token creation requests. Please try again later.",
        )
    limiter.record(client_ip)
    actor = _require_actor(context)
    try:
        raw_token, token = token_service.create_product_token(
            db,
            object_id=object_id,
            name=payload.name,
            token_type=payload.type,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            issued_for=payload.issued_for,
            expires_in_days=payload.expires_in_days,
            actor=actor,
        )
    except token_service.TokenServiceError as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return {"raw_token": raw_token, "token": token}


@router.get("/objects/{object_id}/tokens")
def list_object_tokens(
    object_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_actor(context)
    try:
        items = token_service.list_product_tokens(db, object_id=object_id, actor=actor)
    except token_service.TokenServiceError as exc:
        raise _translate_error(exc) from exc
    return {"items": items, "total": len(items)}


@router.post("/tokens/{token_id}/revoke")
def revoke_object_token(
    token_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    actor = _require_actor(context)
    try:
        token = token_service.revoke_product_token(db, token_id=token_id, actor=actor)
    except token_service.TokenServiceError as exc:
        raise _translate_error(exc) from exc
    db.commit()
    return token
