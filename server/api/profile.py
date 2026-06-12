"""Profile API -- thin route layer that delegates to the profile service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.auth import get_current_access_context, require_role
from server.db import get_db
from server.exceptions import ForbiddenError, NotFoundError
from server.models import User
from server.modules.access.authn import AccessContext
from server.modules.profile import service as profile_service

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])
credentials_router = APIRouter(prefix="/api/v1/credentials", tags=["credentials"])


# ── Profile endpoints ─────────────────────────────────────────────────────────


@router.get("/me")
def profile_me(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    """Return the profile for the currently authenticated user."""
    return profile_service.build_profile(db, context)


@router.get("/{credential_id}")
def profile_admin_view(
    credential_id: int,
    user: User = Depends(require_role("maintainer", "contributor")),
    db: Session = Depends(get_db),
):
    """Return the profile for a specified credential (admin view)."""
    try:
        return profile_service.build_admin_view(db, credential_id=credential_id, user=user)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="credential not found")
    except ForbiddenError:
        raise HTTPException(status_code=403, detail="credential access denied")


# ── Writeback ─────────────────────────────────────────────────────────────────


class WritebackBody(BaseModel):
    note: str = Field(max_length=4096)
    context: dict[str, Any] | None = None


@router.post("/writeback")
def profile_writeback(
    body: WritebackBody,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    """Record a memory writeback event for the authenticated credential."""
    from server.modules.access.authz import require_any_scope

    if not require_any_scope(context, {"api:user", "authoring:write", "skill:write"}):
        raise HTTPException(
            status_code=403, detail="insufficient scope for writeback"
        )

    return profile_service.record_writeback(db, context, body.note, body.context)


# ── Policy update ─────────────────────────────────────────────────────────────


class PolicyUpdateBody(BaseModel):
    max_daily_publishes: int | None = Field(default=None, ge=0, le=10000)
    readonly: bool | None = None
    allowed_object_kinds: list[str] | None = None


@credentials_router.patch("/{credential_id}/policy")
def credential_policy_update(
    credential_id: int,
    body: PolicyUpdateBody,
    user: User = Depends(require_role("maintainer", "contributor")),
    db: Session = Depends(get_db),
):
    """Update policy constraints on a credential's associated AccessGrant."""
    updates: dict[str, Any] = {}
    if body.max_daily_publishes is not None:
        updates["max_daily_publishes"] = body.max_daily_publishes
    if body.readonly is not None:
        updates["readonly"] = body.readonly
    if body.allowed_object_kinds is not None:
        updates["allowed_object_kinds"] = body.allowed_object_kinds

    actor_ref = str(user.id)
    try:
        return profile_service.update_credential_policy(db, credential_id, updates, actor_ref)
    except LookupError:
        raise HTTPException(status_code=404, detail="credential not found")
