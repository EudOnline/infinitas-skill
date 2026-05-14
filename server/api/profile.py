"""Profile API — returns identity, accessible skills, operation history, and policy."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.models import (
    AccessGrant,
    AuditEvent,
    Credential,
    Exposure,
    RegistryObject,
    Release,
)
from server.modules.access.authn import AccessContext

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("/me")
def profile_me(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
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
