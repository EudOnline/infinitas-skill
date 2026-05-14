"""Profile API — returns identity, accessible skills, operation history, and policy."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import get_current_access_context, require_role
from server.db import get_db
from server.models import (
    AccessGrant,
    AuditEvent,
    Credential,
    Exposure,
    Principal,
    RegistryObject,
    Release,
    User,
)
from server.modules.access import service as access_service
from server.modules.access.authn import AccessContext

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])
credentials_router = APIRouter(prefix="/api/v1/credentials", tags=["credentials"])


# ── Shared helper ────────────────────────────────────────────────────────────


def _build_profile(db: Session, context: AccessContext) -> dict[str, Any]:
    """Build the full profile dict for a given access context."""
    credential = context.credential
    principal = context.principal

    # ── Identity ──────────────────────────────────────────────────────────
    scopes = sorted(context.scopes)

    identity = {
        "credential_id": credential.id,
        "credential_type": credential.type,
        "principal_id": principal.id if principal else None,
        "principal_slug": principal.slug if principal else None,
        "principal_kind": principal.kind if principal else None,
        "principal_display_name": principal.display_name if principal else None,
        "scopes": scopes,
        "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
    }

    # ── Accessible Skills ─────────────────────────────────────────────────
    # Find all active grants for this credential, then resolve RegistryObjects
    # via grant -> exposure -> release -> registry_object chain.
    accessible_skills: list[dict] = []
    seen_obj_ids: set[int] = set()

    grant_query = select(AccessGrant).where(
        AccessGrant.state == "active",
    )
    if credential.grant_id is not None:
        grant_query = grant_query.where(AccessGrant.id == credential.grant_id)
    else:
        # Credentials without a grant can still be matched by finding grants
        # whose associated credential (via resource_selector_json) points here.
        grant_query = grant_query.where(
            AccessGrant.id.in_(
                select(Credential.grant_id).where(
                    Credential.id == credential.id,
                    Credential.grant_id.is_not(None),
                )
            )
        )

    for grant in db.scalars(grant_query).all():
        if grant.exposure_id is None:
            continue
        exposure = db.get(Exposure, grant.exposure_id)
        if exposure is None or exposure.state != "active":
            continue
        release = db.get(Release, exposure.release_id)
        if release is None or release.registry_object_id is None:
            continue
        if release.registry_object_id in seen_obj_ids:
            continue
        obj = db.get(RegistryObject, release.registry_object_id)
        if obj is None:
            continue
        seen_obj_ids.add(obj.id)
        accessible_skills.append({
            "id": obj.id,
            "slug": obj.slug,
            "display_name": obj.display_name,
            "kind": obj.kind,
        })

    # ── Operation History ─────────────────────────────────────────────────
    # Last 50 AuditEvents where aggregate_id == str(credential.id)
    agg_id = str(credential.id)
    history_rows = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.aggregate_id == agg_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(50)
    ).all()

    operation_history = []
    for row in history_rows:
        payload = {}
        if row.payload_json:
            try:
                payload = json.loads(row.payload_json)
            except (json.JSONDecodeError, TypeError):
                payload = {}
        operation_history.append({
            "id": row.id,
            "aggregate_type": row.aggregate_type,
            "aggregate_id": row.aggregate_id,
            "event_type": row.event_type,
            "actor_ref": row.actor_ref,
            "payload": payload,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        })

    # ── Policy ────────────────────────────────────────────────────────────
    # constraints_json from the credential's associated AccessGrant
    policy = None
    if credential.grant_id is not None:
        grant = db.get(AccessGrant, credential.grant_id)
        if grant is not None and grant.constraints_json:
            try:
                policy = json.loads(grant.constraints_json)
            except (json.JSONDecodeError, TypeError):
                policy = None

    return {
        "identity": identity,
        "accessible_skills": accessible_skills,
        "operation_history": operation_history,
        "policy": policy,
    }


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/me")
def profile_me(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    """Return the profile for the currently authenticated user."""
    return _build_profile(db, context)


@router.get("/{credential_id}")
def profile_admin_view(
    credential_id: int,
    user: User = Depends(require_role("maintainer", "contributor")),
    db: Session = Depends(get_db),
):
    """Return the profile for a specified credential (admin view).

    Only accessible by users with maintainer or contributor role.
    """
    credential = access_service.resolve_credential_by_id(db, credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="credential not found")

    principal = access_service.get_principal(db, credential.principal_id)
    resolved_user = access_service.get_user_for_principal(db, principal)
    scopes = access_service.parse_scopes(credential.scopes_json)

    synthetic_context = AccessContext(
        credential=credential,
        principal=principal,
        user=resolved_user,
        scopes=scopes,
    )
    return _build_profile(db, synthetic_context)


# ── Writeback ────────────────────────────────────────────────────────────────


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
    credential = context.credential
    actor_ref = context.principal.slug if context.principal else str(credential.id)

    payload = {"note": body.note, "context": body.context}

    event = AuditEvent(
        aggregate_type="memory_writeback",
        aggregate_id=str(credential.id),
        event_type="memory.writeback",
        actor_ref=actor_ref,
        payload_json=json.dumps(payload, ensure_ascii=False),
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    return {"status": "recorded"}


# ── Policy Update ────────────────────────────────────────────────────────────


class PolicyUpdateBody(BaseModel):
    max_daily_publishes: int | None = None
    allowed_object_kinds: list[str] | None = None
    readonly: bool | None = None


@credentials_router.patch("/{credential_id}/policy")
def credential_policy_update(
    credential_id: int,
    body: PolicyUpdateBody,
    user: User = Depends(require_role("maintainer", "contributor")),
    db: Session = Depends(get_db),
):
    """Update policy constraints on a credential's associated AccessGrant.

    If no grant is associated, stores the policy in the credential's
    resource_selector_json under the ``_policy`` key.
    """
    credential = access_service.resolve_credential_by_id(db, credential_id)
    if credential is None:
        raise HTTPException(status_code=404, detail="credential not found")

    updates: dict[str, Any] = {}
    if body.max_daily_publishes is not None:
        updates["max_daily_publishes"] = body.max_daily_publishes
    if body.allowed_object_kinds is not None:
        updates["allowed_object_kinds"] = body.allowed_object_kinds
    if body.readonly is not None:
        updates["readonly"] = body.readonly

    if not updates:
        # Nothing to update — return current policy
        current = _get_current_policy(db, credential)
        return {"status": "updated", "policy": current}

    if credential.grant_id is not None:
        grant = db.get(AccessGrant, credential.grant_id)
        if grant is not None:
            existing: dict[str, Any] = {}
            if grant.constraints_json:
                try:
                    existing = json.loads(grant.constraints_json)
                except (json.JSONDecodeError, TypeError):
                    existing = {}
            existing.update(updates)
            grant.constraints_json = json.dumps(existing, ensure_ascii=False)
            db.add(grant)
            db.commit()
            db.refresh(grant)
            policy = json.loads(grant.constraints_json)
            return {"status": "updated", "policy": policy}

    # No grant — store in credential.resource_selector_json under _policy
    rs: dict[str, Any] = {}
    if credential.resource_selector_json:
        try:
            rs = json.loads(credential.resource_selector_json)
        except (json.JSONDecodeError, TypeError):
            rs = {}

    current_policy = rs.get("_policy", {})
    current_policy.update(updates)
    rs["_policy"] = current_policy

    credential.resource_selector_json = json.dumps(rs, ensure_ascii=False)
    db.add(credential)
    db.commit()
    db.refresh(credential)

    updated_rs = json.loads(credential.resource_selector_json)
    return {"status": "updated", "policy": updated_rs.get("_policy")}


def _get_current_policy(db: Session, credential: Credential) -> dict[str, Any] | None:
    """Return the current policy dict for a credential, or None."""
    if credential.grant_id is not None:
        grant = db.get(AccessGrant, credential.grant_id)
        if grant is not None and grant.constraints_json:
            try:
                return json.loads(grant.constraints_json)
            except (json.JSONDecodeError, TypeError):
                return None
    # Check resource_selector_json._policy
    if credential.resource_selector_json:
        try:
            rs = json.loads(credential.resource_selector_json)
            return rs.get("_policy")
        except (json.JSONDecodeError, TypeError):
            return None
    return None
