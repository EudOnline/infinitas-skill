"""Profile API -- thin route layer that delegates to the profile service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import server.modules.identity.profile_service as profile_service
from server.db import get_db
from server.exceptions import ForbiddenError, NotFoundError
from server.modules.access.authn import AccessContext
from server.modules.identity.auth import get_current_access_context
from server.modules.identity.guards import require_admin_actor_ref
from server.modules.identity.models import User
from server.modules.identity.profile_schemas import (
    CredentialPolicyUpdateView,
    CredentialProfileView,
)

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])
credentials_router = APIRouter(prefix="/api/v1/credentials", tags=["credentials"])


def _admin_user(
    context: AccessContext = Depends(get_current_access_context),
) -> User:
    require_admin_actor_ref(context)
    if context.user is None:
        raise HTTPException(status_code=403, detail="admin credential required")
    return context.user


# ── Profile endpoints ─────────────────────────────────────────────────────────


@router.get(
    "/me",
    response_model=CredentialProfileView,
)
def profile_me(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the profile for the currently authenticated user."""
    return profile_service.build_profile(db, context)


@router.get(
    "/{credential_id}",
    response_model=CredentialProfileView,
)
def profile_admin_view(
    credential_id: int,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the profile for a specified credential (admin view)."""
    try:
        return profile_service.build_admin_view(db, credential_id=credential_id, user=user)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="credential not found")
    except ForbiddenError:
        raise HTTPException(status_code=403, detail="credential access denied")


# ── Policy update ─────────────────────────────────────────────────────────────


class PolicyUpdateBody(BaseModel):
    max_daily_publishes: int | None = Field(default=None, ge=0, le=10000)
    readonly: bool | None = None
    allowed_object_kinds: list[str] | None = None


@credentials_router.patch(
    "/{credential_id}/policy",
    response_model=CredentialPolicyUpdateView,
)
def credential_policy_update(
    credential_id: int,
    body: PolicyUpdateBody,
    user: User = Depends(_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update policy constraints on a credential's associated AccessGrant."""
    updates: dict[str, Any] = {}
    if body.max_daily_publishes is not None:
        updates["max_daily_publishes"] = body.max_daily_publishes
    if body.readonly is not None:
        updates["readonly"] = body.readonly
    if body.allowed_object_kinds is not None:
        updates["allowed_object_kinds"] = body.allowed_object_kinds

    try:
        return profile_service.update_credential_policy(db, credential_id, updates, user)
    except LookupError:
        raise HTTPException(status_code=404, detail="credential not found")
    except ForbiddenError:
        raise HTTPException(status_code=403, detail="credential policy access denied")
