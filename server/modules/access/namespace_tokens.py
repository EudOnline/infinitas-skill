from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

import server.modules.access.token_service as token_service
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.schemas import (
    ProductTokenCreateView,
    ProductTokenListView,
    ProductTokenView,
)
from server.modules.identity.auth import get_current_access_context
from server.modules.identity.guards import require_session_actor_ref
from server.modules.shared.actor import ActorRef
from server.rate_limit import get_rate_limiter, resolve_client_ip

router = APIRouter(prefix="/api/v1/namespace-tokens", tags=["namespace-tokens"])


class NamespaceTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["reader", "publisher"]
    issued_for: str | None = Field(default=None, max_length=200)
    expires_in_days: int = Field(default=90, ge=1, le=3650)
    max_daily_publishes: int | None = Field(default=None, ge=1, le=100000)

    @model_validator(mode="after")
    def validate_publish_limit(self) -> "NamespaceTokenCreateRequest":
        if self.type == "reader" and self.max_daily_publishes is not None:
            raise ValueError("readers cannot set max_daily_publishes")
        return self


def _actor(context: AccessContext) -> ActorRef:
    return require_session_actor_ref(context)


@router.post("", response_model=ProductTokenCreateView, status_code=status.HTTP_201_CREATED)
def create_namespace_token(
    payload: NamespaceTokenCreateRequest,
    request: Request,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not get_rate_limiter(db).consume(
        f"namespace-token:{resolve_client_ip(request)}",
        max_attempts=20,
        window_seconds=60,
    ):
        raise HTTPException(status_code=429, detail="Too many token creation requests")
    try:
        raw_token, token = token_service.create_namespace_token(
            db,
            name=payload.name,
            token_type=payload.type,
            issued_for=payload.issued_for,
            expires_in_days=payload.expires_in_days,
            max_daily_publishes=payload.max_daily_publishes,
            actor=_actor(context),
        )
    except token_service.TokenServiceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"raw_token": raw_token, "token": token}


@router.get("", response_model=ProductTokenListView)
def list_namespace_tokens(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    items = token_service.list_namespace_tokens(db, actor=_actor(context))
    return {"items": items, "total": len(items)}


@router.post("/{token_id}/revoke", response_model=ProductTokenView)
def revoke_namespace_token(
    token_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return token_service.revoke_namespace_token(db, token_id=token_id, actor=_actor(context))
    except token_service.TokenNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except token_service.TokenForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
