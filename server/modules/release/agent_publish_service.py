from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import server.modules.release.service as release_service
from server.jobs import enqueue_job, has_active_job
from server.model_base import utcnow
from server.modules.access.authn import AccessContext
from server.modules.access.credential_policy import (
    CredentialPolicyForbidden,
    CredentialPublishQuotaExceeded,
    consume_publish_quota_for_principal,
)
from server.modules.access.product_scope import (
    ProductScopeForbidden,
    assert_product_token_skill_scope,
)
from server.modules.audit.service import append_audit_event
from server.modules.authoring.models import SkillVersion
from server.modules.exposure.models import Exposure
from server.modules.identity.models import ServicePrincipal
from server.modules.release.models import AgentPublishIntent, Release


class AgentPublishError(Exception):
    pass


class AgentPublishForbidden(AgentPublishError):
    pass


class AgentPublishNotFound(AgentPublishError):
    pass


class AgentPublishConflict(AgentPublishError):
    pass


def _policy(service: ServicePrincipal) -> dict:
    try:
        payload = json.loads(service.policy_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def create_or_get_publish_intent(
    db: Session,
    *,
    version_id: int,
    context: AccessContext,
) -> tuple[AgentPublishIntent, Release, bool]:
    if context.credential.type != "agent_token" or context.principal is None:
        raise AgentPublishForbidden("agent credential required")
    service = db.scalar(
        select(ServicePrincipal).where(ServicePrincipal.principal_id == context.principal.id)
    )
    if service is None or service.state != "active":
        raise AgentPublishForbidden("agent is not active")
    version = db.get(SkillVersion, version_id)
    if version is None:
        raise AgentPublishNotFound("skill version not found")
    try:
        assert_product_token_skill_scope(db, context=context, skill_id=version.skill_id)
    except ProductScopeForbidden as exc:
        raise AgentPublishForbidden(str(exc)) from exc
    try:
        from server.modules.access.credential_policy import assert_agent_publish_allowed

        assert_agent_publish_allowed(db, service=service, object_kind="skill")
    except CredentialPolicyForbidden as exc:
        raise AgentPublishForbidden(str(exc)) from exc

    existing = db.scalar(
        select(AgentPublishIntent)
        .where(AgentPublishIntent.principal_id == context.principal.id)
        .join(Release, Release.id == AgentPublishIntent.release_id)
        .where(Release.skill_version_id == version_id)
    )
    if existing is not None:
        release = db.get(Release, existing.release_id)
        if release is None:
            raise AgentPublishConflict("publish intent release is missing")
        return existing, release, False

    try:
        release, _ = release_service.create_or_get_release(
            db,
            version_id=version_id,
            actor_principal_id=context.principal.id,
            audit_actor=None,
        )
    except release_service.ReleaseError as exc:
        raise AgentPublishConflict(str(exc)) from exc

    policy = _policy(service)
    intent = AgentPublishIntent(
        release_id=release.id,
        principal_id=context.principal.id,
        credential_id=context.credential.id,
        policy_snapshot_json=json.dumps(policy, sort_keys=True),
        audience_type="public",
        listing_mode="listed",
        install_mode="enabled",
        state="pending",
        quota_key=f"agent-publish:{context.principal.id}",
    )
    try:
        with db.begin_nested():
            db.add(intent)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(AgentPublishIntent).where(AgentPublishIntent.release_id == release.id)
        )
        if existing is None:
            raise AgentPublishConflict("publish intent already exists")
        return existing, release, False

    # Consume only after the idempotency row wins the race. The quota is keyed
    # to the service principal, so credential rotation cannot reset it.
    try:
        intent.quota_key = consume_publish_quota_for_principal(
            db, principal_id=context.principal.id, service=service
        )
    except CredentialPublishQuotaExceeded:
        intent.state = "suppressed"
        intent.reason = "daily publish quota exceeded"
        raise

    if not has_active_job(db, kind="materialize_release", release_id=release.id):
        enqueue_job(
            db,
            kind="materialize_release",
            payload={"release_id": release.id, "publish_intent_id": intent.id},
            release_id=release.id,
            requested_by=context.principal,
            note=f"materialize Agent release {release.id}",
        )
    return intent, release, True


def finalize_publish_intent(db: Session, *, intent_id: int) -> AgentPublishIntent:
    """Apply the Agent's public policy after release materialization.

    This is deliberately evaluated in the worker transaction: an Agent can be
    suspended or have auto-public disabled while artifacts are being built.
    """
    intent = db.scalar(
        select(AgentPublishIntent).where(AgentPublishIntent.id == intent_id).with_for_update()
    )
    if intent is None:
        raise AgentPublishConflict("publish intent not found")
    if intent.state in {"activated", "suppressed"}:
        return intent
    service = db.scalar(
        select(ServicePrincipal).where(ServicePrincipal.principal_id == intent.principal_id)
    )
    release = db.get(Release, intent.release_id)
    if release is None:
        intent.state = "suppressed"
        intent.reason = "release not found"
        return intent
    policy = _policy(service) if service is not None else {}
    blocked = None
    if service is None or service.state != "active":
        blocked = "agent is no longer active"
    elif policy.get("auto_public_publish") is not True:
        blocked = "auto public publish is disabled"
    elif release.state != "ready":
        blocked = "release is not ready"
    else:
        try:
            compatibility = json.loads(release.platform_compatibility_json or "{}")
        except json.JSONDecodeError:
            compatibility = {}
        canonical = (
            compatibility.get("canonical_runtime") if isinstance(compatibility, dict) else None
        )
        if isinstance(canonical, dict) and canonical.get("state") in {
            "blocked",
            "broken",
            "unsupported",
        }:
            blocked = "public visibility is blocked by runtime compatibility"
    if blocked is not None:
        intent.state = "suppressed"
        intent.reason = blocked
        db.add(intent)
        db.flush()
        return intent

    exposure = db.scalar(
        select(Exposure)
        .where(Exposure.release_id == release.id)
        .where(Exposure.audience_type == "public")
        .where(Exposure.state.notin_(["revoked", "rejected"]))
        .with_for_update()
    )
    if exposure is None:
        exposure = Exposure(
            release_id=release.id,
            audience_type="public",
            listing_mode="listed",
            install_mode="enabled",
            review_requirement="none",
            state="active",
            requested_by_principal_id=intent.principal_id,
            policy_snapshot_json=json.dumps(
                {"source": "agent_publish_intent", "intent_id": intent.id, "policy": policy},
                sort_keys=True,
            ),
            activated_at=utcnow(),
        )
        db.add(exposure)
        try:
            with db.begin_nested():
                db.flush()
        except IntegrityError:
            exposure = db.scalar(
                select(Exposure)
                .where(Exposure.release_id == release.id)
                .where(Exposure.audience_type == "public")
                .where(Exposure.state.notin_(["revoked", "rejected"]))
            )
    intent.state = "activated"
    setattr(intent, "activated_at", utcnow())
    intent.reason = ""
    db.add(intent)
    db.flush()
    snapshot = release_service.get_release_snapshot(db, release.id)
    append_audit_event(
        db,
        aggregate_type="exposure",
        aggregate_id=str(exposure.id if exposure is not None else release.id),
        event_type="exposure.activated",
        actor_ref=f"agent:{intent.principal_id}",
        owner_principal_id=snapshot.skill.namespace_id,
        payload={"release_id": release.id, "intent_id": intent.id, "audience_type": "public"},
    )
    return intent


__all__ = [
    "create_or_get_publish_intent",
    "finalize_publish_intent",
    "AgentPublishError",
    "AgentPublishForbidden",
    "AgentPublishNotFound",
    "AgentPublishConflict",
]
