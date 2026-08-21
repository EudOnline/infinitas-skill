from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import server.modules.audit.service as audit_service
import server.modules.identity.service as identity_service
from server.model_base import utcnow
from server.modules.identity.agent_shared import (
    AgentEnrollmentConflict,
    AgentEnrollmentNotFound,
    credential_fingerprint,
)
from server.modules.identity.agent_shared import (
    active_invitation_for_reservation as _active_invitation_for_reservation,
)
from server.modules.identity.agent_shared import (
    enrollment_public_id as _public_id,
)
from server.modules.identity.agent_shared import (
    enrollment_token as _token,
)
from server.modules.identity.agent_shared import (
    validate_invitation_request_nonce as _validate_invitation_request_nonce,
)
from server.modules.identity.models import (
    AgentEnrollment,
    AgentInvitation,
    AgentNamespaceReservation,
    Credential,
    Principal,
    ServicePrincipal,
)

_AGENT_SCOPES = {"agent:publish", "artifact:download", "release:read", "registry:publish"}


def _actor_ref(principal_id: int) -> str:
    return f"principal:{principal_id}"


def _audit(
    db: Session,
    *,
    event_type: str,
    aggregate_id: int | str,
    actor_principal_id: int,
    owner_principal_id: int | None = None,
    payload: dict | None = None,
) -> None:
    audit_service.append_audit_event(
        db,
        aggregate_type="agent",
        aggregate_id=str(aggregate_id),
        event_type=event_type,
        actor_ref=_actor_ref(actor_principal_id),
        owner_principal_id=owner_principal_id,
        payload=payload,
    )


def revoke_invitation(
    db: Session, *, invitation_id: int, actor_principal_id: int
) -> AgentInvitation:
    invitation = db.get(AgentInvitation, invitation_id)
    if invitation is None:
        raise AgentEnrollmentNotFound("invitation not found")
    now = utcnow()
    result = db.execute(
        update(AgentInvitation)
        .where(AgentInvitation.id == invitation_id, AgentInvitation.state == "open")
        .values(state="revoked", revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        raise AgentEnrollmentConflict("only an open invitation can be revoked")
    _audit(
        db,
        event_type="agent.invitation.revoked",
        aggregate_id=invitation.public_id,
        actor_principal_id=actor_principal_id,
        payload={"purpose": invitation.purpose},
    )
    return invitation


def release_reservation(
    db: Session, *, reservation_id: int, actor_principal_id: int
) -> AgentNamespaceReservation:
    reservation = db.get(AgentNamespaceReservation, reservation_id)
    if reservation is None:
        raise AgentEnrollmentNotFound("namespace reservation not found")
    if reservation.state != "reserved":
        raise AgentEnrollmentConflict("only an unclaimed reservation can be released")
    if _active_invitation_for_reservation(db, reservation.id) is not None:
        raise AgentEnrollmentConflict(
            "revoke the open invitation before releasing this reservation"
        )
    pending = db.scalar(
        select(AgentEnrollment)
        .join(AgentInvitation, AgentInvitation.id == AgentEnrollment.invitation_id)
        .where(
            AgentInvitation.reservation_id == reservation.id,
            AgentEnrollment.state == "pending",
        )
    )
    if pending is not None:
        raise AgentEnrollmentConflict(
            "reject the pending enrollment before releasing this reservation"
        )
    reservation.state = "released"
    reservation.released_by_principal_id = actor_principal_id
    reservation.released_at = utcnow()
    _audit(
        db,
        event_type="agent.reservation.released",
        aggregate_id=reservation.id,
        actor_principal_id=actor_principal_id,
        payload={"slug": reservation.slug},
    )
    return reservation


def transition_agent(
    db: Session, *, service_id: int, action: str, actor_principal_id: int
) -> ServicePrincipal:
    service = db.get(ServicePrincipal, service_id)
    if service is None or service.enrollment_id is None:
        raise AgentEnrollmentNotFound("Agent not found")
    transitions = {
        ("active", "suspend"): "suspended",
        ("suspended", "resume"): "active",
        ("active", "revoke"): "revoked",
        ("suspended", "revoke"): "revoked",
    }
    target = transitions.get((service.state, action))
    if target is None:
        raise AgentEnrollmentConflict(f"cannot {action} an Agent in state {service.state}")
    now = utcnow()
    result = db.execute(
        update(ServicePrincipal)
        .where(ServicePrincipal.id == service.id, ServicePrincipal.state == service.state)
        .values(
            state=target,
            suspended_at=now if target == "suspended" else None,
            revoked_at=now if target == "revoked" else service.revoked_at,
        )
        .execution_options(synchronize_session=False)
    )
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        raise AgentEnrollmentConflict("Agent state changed concurrently")
    if target == "revoked":
        identity_service.revoke_principal_credentials(
            db, principal_id=service.principal_id, credential_types={"agent_token"}
        )
    _audit(
        db,
        event_type=f"agent.{target}",
        aggregate_id=service.id,
        actor_principal_id=actor_principal_id,
        owner_principal_id=service.principal_id,
        payload={"slug": service.slug, "previous_state": service.state},
    )
    return service


def create_recovery_invitation(
    db: Session,
    *,
    service_id: int,
    request_nonce: str,
    expires_in_minutes: int,
    actor_principal_id: int,
    base_url: str,
) -> tuple[AgentInvitation, str, str]:
    service = db.get(ServicePrincipal, service_id)
    if service is None or service.enrollment_id is None:
        raise AgentEnrollmentNotFound("Agent not found")
    if service.state not in {"active", "suspended"}:
        raise AgentEnrollmentConflict("recovery is unavailable for a revoked Agent")
    reservation = db.scalar(
        select(AgentNamespaceReservation).where(
            AgentNamespaceReservation.claimed_service_principal_id == service.id
        )
    )
    if reservation is None or reservation.state != "claimed":
        raise AgentEnrollmentConflict("claimed Agent namespace not found")
    normalized_nonce = _validate_invitation_request_nonce(request_nonce)
    nonce_hash = identity_service.hash_token(normalized_nonce)
    if db.scalar(select(AgentInvitation).where(AgentInvitation.request_nonce_hash == nonce_hash)):
        raise AgentEnrollmentConflict("invitation request has already been used")
    db.execute(
        update(AgentInvitation)
        .where(AgentInvitation.reservation_id == reservation.id)
        .where(AgentInvitation.state == "open")
        .where(AgentInvitation.expires_at <= utcnow())
        .values(state="expired")
    )
    if _active_invitation_for_reservation(db, reservation.id) is not None:
        raise AgentEnrollmentConflict("an invitation is already open for this Agent")
    raw = _token("enroll_")
    invitation = AgentInvitation(
        public_id=_public_id("ainv_"),
        reservation_id=reservation.id,
        purpose="recover",
        target_service_principal_id=service.id,
        invitation_hash=identity_service.hash_token(raw),
        request_nonce_hash=nonce_hash,
        policy_json=service.policy_json,
        state="open",
        expires_at=utcnow() + timedelta(minutes=expires_in_minutes),
        created_by_principal_id=actor_principal_id,
    )
    try:
        with db.begin_nested():
            db.add(invitation)
            db.flush()
    except IntegrityError as exc:
        raise AgentEnrollmentConflict(
            "an invitation is already open or this request was already used"
        ) from exc
    prompt = (
        f"Recover Infinitas Agent {service.slug}.\n"
        "Read this invitation from stdin without echoing it, then run:\n"
        f"infinitas agent join --base-url {base_url.rstrip('/')} --enrollment-token-stdin\n"
        "The existing Agent key will be replaced only after maintainer approval."
    )
    _audit(
        db,
        event_type="agent.recovery_invitation.created",
        aggregate_id=service.id,
        actor_principal_id=actor_principal_id,
        owner_principal_id=service.principal_id,
        payload={"invitation_public_id": invitation.public_id},
    )
    return invitation, raw, prompt


def approve_recovery(
    db: Session,
    *,
    enrollment: AgentEnrollment,
    invitation: AgentInvitation,
    actor_principal_id: int,
    note: str,
) -> AgentEnrollment:
    service = db.get(ServicePrincipal, invitation.target_service_principal_id)
    if service is None or service.state not in {"active", "suspended"}:
        raise AgentEnrollmentConflict("recovery target is unavailable")
    now = utcnow()
    result = db.execute(
        update(AgentEnrollment)
        .where(AgentEnrollment.id == enrollment.id, AgentEnrollment.state == "pending")
        .values(
            state="approved",
            decision_by_principal_id=actor_principal_id,
            decided_at=now,
            decision_note=note,
        )
        .execution_options(synchronize_session=False)
    )
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        raise AgentEnrollmentConflict("enrollment was decided concurrently")
    identity_service.revoke_principal_credentials(
        db, principal_id=service.principal_id, credential_types={"agent_token"}
    )
    credential = Credential(
        principal_id=service.principal_id,
        type="agent_token",
        hashed_secret=enrollment.proposed_api_key_hash,
        scopes_json=identity_service.encode_scopes(_AGENT_SCOPES),
        resource_selector_json=json.dumps({"namespace_id": service.principal_id}, sort_keys=True),
        product_scope_type="namespace",
        product_scope_id=service.principal_id,
        product_token_type="publisher",  # noqa: S106
        product_token_name=f"agent:{service.slug}",
        created_at=now,
    )
    db.add(credential)
    _audit(
        db,
        event_type="agent.recovered",
        aggregate_id=service.id,
        actor_principal_id=actor_principal_id,
        owner_principal_id=service.principal_id,
        payload={"enrollment_public_id": enrollment.public_id},
    )
    return enrollment


def rotate_agent_credential(
    db: Session,
    *,
    current_credential: Credential,
    principal: Principal,
    api_key_verifier: str,
    fingerprint: str,
    request_id: str,
) -> Credential:
    service = identity_service.get_service_principal(db, principal.id)
    if current_credential.type != "agent_token" or service is None or service.state != "active":
        raise AgentEnrollmentConflict("active Agent credential required")
    canonical = str(api_key_verifier or "").strip()
    if credential_fingerprint(canonical) != fingerprint:
        raise AgentEnrollmentConflict("credential fingerprint mismatch")
    if canonical == current_credential.hashed_secret:
        raise AgentEnrollmentConflict("replacement credential must be different")
    replacement = Credential(
        principal_id=principal.id,
        type="agent_token",
        hashed_secret=canonical,
        scopes_json=current_credential.scopes_json,
        resource_selector_json=current_credential.resource_selector_json,
        product_scope_type=current_credential.product_scope_type,
        product_scope_id=current_credential.product_scope_id,
        product_token_type=current_credential.product_token_type,
        product_token_name=current_credential.product_token_name,
        created_at=utcnow(),
    )
    db.add(replacement)
    db.flush()
    result = db.execute(
        update(Credential)
        .where(Credential.id == current_credential.id, Credential.revoked_at.is_(None))
        .values(revoked_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        raise AgentEnrollmentConflict("Agent credential was rotated concurrently")
    _audit(
        db,
        event_type="agent.credential.rotated",
        aggregate_id=service.id,
        actor_principal_id=principal.id,
        owner_principal_id=principal.id,
        payload={
            "old_credential_id": current_credential.id,
            "new_credential_id": replacement.id,
            "request_id": request_id,
        },
    )
    return replacement


def list_agents(db: Session) -> list[tuple[ServicePrincipal, Principal]]:
    rows = db.execute(
        select(ServicePrincipal, Principal)
        .join(Principal, Principal.id == ServicePrincipal.principal_id)
        .where(ServicePrincipal.enrollment_id.is_not(None))
        .order_by(ServicePrincipal.created_at.asc())
    ).all()
    return [(service, principal) for service, principal in rows]


def list_reservations(db: Session) -> list[AgentNamespaceReservation]:
    query = select(AgentNamespaceReservation).order_by(AgentNamespaceReservation.id)
    return list(db.scalars(query))


def list_invitations(db: Session) -> list[AgentInvitation]:
    return list(db.scalars(select(AgentInvitation).order_by(AgentInvitation.id.desc())))
