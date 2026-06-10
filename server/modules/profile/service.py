"""Profile service -- business logic for identity, accessible skills, operation history, and policy."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import (
    AccessGrant,
    AuditEvent,
    Credential,
    Exposure,
    Release,
    Skill,
)
from server.modules.access import service as access_service
from server.modules.access.authn import AccessContext


# ── Profile builder ───────────────────────────────────────────────────────────


def build_profile(db: Session, context: AccessContext) -> dict[str, Any]:
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
    accessible_skills = _resolve_accessible_skills(db, credential)

    # ── Operation History ─────────────────────────────────────────────────
    operation_history = _resolve_operation_history(db, credential)

    # ── Policy ────────────────────────────────────────────────────────────
    policy = _resolve_policy(db, credential)

    return {
        "identity": identity,
        "accessible_skills": accessible_skills,
        "operation_history": operation_history,
        "policy": policy,
    }


# ── Admin view ────────────────────────────────────────────────────────────────


def build_admin_view(db: Session, *, credential_id: int, user) -> dict[str, Any]:
    """Build a profile dict for an admin looking up another credential.

    Raises ValueError with an explanatory message on authz failures.
    Raises LookupError when the credential is not found.
    """
    from server.auth import require_role  # noqa: delayed import avoids circulars

    credential = access_service.resolve_credential_by_id(db, credential_id)
    if credential is None:
        raise LookupError("credential not found")

    caller_principal = access_service.get_principal_for_user(db, user)
    caller_principal_id = caller_principal.id if caller_principal is not None else 0
    is_maintainer = user.role == "maintainer"
    if not is_maintainer and credential.principal_id != caller_principal_id:
        raise PermissionError("credential access denied")

    principal = access_service.get_principal(db, credential.principal_id)
    resolved_user = access_service.get_user_for_principal(db, principal)
    scopes = access_service.parse_scopes(credential.scopes_json)

    synthetic_context = AccessContext(
        credential=credential,
        principal=principal,
        user=resolved_user,
        scopes=scopes,
    )
    return build_profile(db, synthetic_context)


# ── Policy update ─────────────────────────────────────────────────────────────


def update_credential_policy(
    db: Session,
    credential_id: int,
    updates: dict[str, Any],
    actor_ref: str,
) -> dict[str, Any]:
    """Apply policy updates to a credential's grant or fallback storage.

    Returns {"status": "updated", "policy": ...}.
    Raises LookupError when the credential is not found.
    """
    credential = access_service.resolve_credential_by_id(db, credential_id)
    if credential is None:
        raise LookupError("credential not found")

    if not updates:
        current = get_current_policy(db, credential)
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

    # No grant -- store in credential.resource_selector_json under _policy
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


def record_writeback(
    db: Session,
    context: AccessContext,
    note: str,
    extra_context: dict[str, Any] | None,
) -> dict[str, str]:
    """Record a memory writeback audit event."""
    credential = context.credential
    actor_ref = context.principal.slug if context.principal else str(credential.id)

    payload: dict[str, Any] = {"note": note, "context": extra_context}

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


# ── Helpers ───────────────────────────────────────────────────────────────────


def get_current_policy(db: Session, credential: Credential) -> dict[str, Any] | None:
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


def _resolve_accessible_skills(db: Session, credential: Credential) -> list[dict]:
    """Resolve all skills accessible through this credential's grants."""
    seen_skill_ids: set[int] = set()
    skills: list[dict] = []

    grant_query = select(AccessGrant).where(
        AccessGrant.state == "active",
    )
    if credential.grant_id is not None:
        grant_query = grant_query.where(AccessGrant.id == credential.grant_id)
    else:
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
        if release is None or release.skill_id is None:
            continue
        if release.skill_id in seen_skill_ids:
            continue
        skill = db.get(Skill, release.skill_id)
        if skill is None:
            continue
        seen_skill_ids.add(skill.id)
        skills.append({
            "id": skill.id,
            "slug": skill.slug,
            "display_name": skill.display_name,
            "kind": "skill",
        })

    return skills


def _resolve_operation_history(db: Session, credential: Credential) -> list[dict]:
    """Return the last 50 audit events for this credential."""
    agg_id = str(credential.id)
    history_rows = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.aggregate_id == agg_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(50)
    ).all()

    result = []
    for row in history_rows:
        payload = {}
        if row.payload_json:
            try:
                payload = json.loads(row.payload_json)
            except (json.JSONDecodeError, TypeError):
                payload = {}
        result.append({
            "id": row.id,
            "aggregate_type": row.aggregate_type,
            "aggregate_id": row.aggregate_id,
            "event_type": row.event_type,
            "actor_ref": row.actor_ref,
            "payload": payload,
            "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
        })

    return result


def _resolve_policy(db: Session, credential: Credential) -> dict[str, Any] | None:
    """Resolve the policy from the credential's associated grant."""
    if credential.grant_id is not None:
        grant = db.get(AccessGrant, credential.grant_id)
        if grant is not None and grant.constraints_json:
            try:
                return json.loads(grant.constraints_json)
            except (json.JSONDecodeError, TypeError):
                return None
    return None
