from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

import server.modules.identity.service as identity_service
from server.model_base import utcnow
from server.modules.identity.models import (
    AgentEnrollment,
    AgentInvitation,
    AgentNamespaceReservation,
    Credential,
    Principal,
    ServicePrincipal,
)


class AgentEnrollmentError(Exception):
    pass


class AgentEnrollmentNotFound(AgentEnrollmentError):
    pass


class AgentEnrollmentConflict(AgentEnrollmentError):
    pass


def _token(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(32)}"


def _public_id(prefix: str) -> str:
    return f"{prefix}{secrets.token_urlsafe(18)}"


def _canonical_verifier(value: str) -> str:
    normalized = str(value or "").strip()
    if len(normalized) != 71 or not normalized.startswith("sha256:"):
        raise AgentEnrollmentConflict("invalid credential verifier")
    try:
        int(normalized[7:], 16)
    except ValueError as exc:
        raise AgentEnrollmentConflict("invalid credential verifier") from exc
    return normalized


def credential_fingerprint(verifier: str) -> str:
    canonical = _canonical_verifier(verifier)
    return hashlib.sha256(f"infinitas-agent-fingerprint-v1\0{canonical}".encode()).hexdigest()[:16]


def _iso(value: Any) -> str:
    return value.isoformat() if value is not None else ""


def _active_invitation_for_reservation(db: Session, reservation_id: int) -> AgentInvitation | None:
    return db.scalar(
        select(AgentInvitation)
        .where(AgentInvitation.reservation_id == reservation_id)
        .where(AgentInvitation.state == "open")
        .where(AgentInvitation.expires_at > utcnow())
    )


def create_invitation(
    db: Session,
    *,
    slug: str,
    display_name: str,
    expires_in_minutes: int,
    max_daily_publishes: int,
    auto_public_publish: bool,
    creator_principal_id: int,
    base_url: str,
) -> tuple[AgentInvitation, str, str]:
    normalized_slug = slug.strip().lower()
    reservation = db.scalar(
        select(AgentNamespaceReservation).where(AgentNamespaceReservation.slug == normalized_slug)
    )
    if reservation is None:
        reservation = AgentNamespaceReservation(
            slug=normalized_slug,
            display_name=display_name.strip(),
            state="reserved",
            created_by_principal_id=creator_principal_id,
        )
        db.add(reservation)
        db.flush()
    elif reservation.state != "reserved":
        raise AgentEnrollmentConflict("agent slug is already claimed or released")
    if _active_invitation_for_reservation(db, reservation.id) is not None:
        raise AgentEnrollmentConflict("an invitation is already open for this agent")

    raw = _token("enroll_")
    invitation = AgentInvitation(
        public_id=_public_id("ainv_"),
        reservation_id=reservation.id,
        purpose="enroll",
        invitation_hash=identity_service.hash_token(raw),
        policy_json=json.dumps(
            {
                "max_daily_publishes": max_daily_publishes,
                "auto_public_publish": auto_public_publish,
                "allowed_object_kinds": ["skill"],
            },
            sort_keys=True,
        ),
        state="open",
        expires_at=utcnow() + timedelta(minutes=expires_in_minutes),
        created_by_principal_id=creator_principal_id,
    )
    db.add(invitation)
    db.flush()
    normalized_base = base_url.rstrip("/")
    prompt = (
        f"Join Infinitas Agent {normalized_slug}.\n"
        f"Read this invitation from stdin without echoing it, then run:\n"
        f"infinitas agent join --base-url {normalized_base} --enrollment-token-stdin\n"
        "The invitation is single-use and expires soon. Never place it in argv, logs, "
        "URLs, or chat output."
    )
    return invitation, raw, prompt


def _find_invitation_by_token(db: Session, raw_token: str) -> AgentInvitation:
    token = str(raw_token or "").strip()
    if not token.startswith("enroll_"):
        raise AgentEnrollmentNotFound("invalid enrollment token")
    invitation = db.scalar(
        select(AgentInvitation).where(
            AgentInvitation.invitation_hash == identity_service.hash_token(token)
        )
    )
    if invitation is None:
        raise AgentEnrollmentNotFound("invalid enrollment token")
    if invitation.state != "open":
        raise AgentEnrollmentConflict("invitation has already been consumed")
    if invitation.expires_at <= utcnow():
        invitation.state = "expired"
        raise AgentEnrollmentConflict("invitation has expired")
    return invitation


def submit_enrollment(
    db: Session,
    *,
    raw_invitation: str,
    status_verifier: str,
    api_key_verifier: str,
    fingerprint: str,
    runtime: dict[str, Any],
) -> AgentEnrollment:
    invitation = _find_invitation_by_token(db, raw_invitation)
    status_hash = _canonical_verifier(status_verifier)
    api_hash = _canonical_verifier(api_key_verifier)
    expected_fingerprint = credential_fingerprint(api_hash)
    if fingerprint != expected_fingerprint:
        raise AgentEnrollmentConflict("credential fingerprint mismatch")
    now = utcnow()
    result = db.execute(
        update(AgentInvitation)
        .where(
            and_(
                AgentInvitation.id == invitation.id,
                AgentInvitation.state == "open",
                AgentInvitation.expires_at > now,
            )
        )
        .values(state="consumed", consumed_at=now)
    )
    changed = int(getattr(result, "rowcount", 0) or 0)
    if changed != 1:
        raise AgentEnrollmentConflict("invitation was consumed concurrently")
    enrollment = AgentEnrollment(
        public_id=_public_id("aenr_"),
        invitation_id=invitation.id,
        status_hash=status_hash,
        proposed_api_key_hash=api_hash,
        fingerprint=expected_fingerprint,
        runtime_metadata_json=json.dumps(runtime or {}, ensure_ascii=False, sort_keys=True),
        state="pending",
    )
    db.add(enrollment)
    db.flush()
    return enrollment


def _get_enrollment_by_status(db: Session, token: str) -> AgentEnrollment:
    if not str(token or "").startswith("status_"):
        raise AgentEnrollmentNotFound("invalid status token")
    hashed = identity_service.hash_token(str(token).strip())
    enrollment = db.scalar(select(AgentEnrollment).where(AgentEnrollment.status_hash == hashed))
    if enrollment is None:
        raise AgentEnrollmentNotFound("invalid status token")
    return enrollment


def status_for_token(
    db: Session, token: str
) -> tuple[AgentEnrollment, AgentInvitation, Principal | None]:
    enrollment = _get_enrollment_by_status(db, token)
    invitation = db.get(AgentInvitation, enrollment.invitation_id)
    if invitation is None:
        raise AgentEnrollmentNotFound("enrollment invitation not found")
    principal = None
    service = db.scalar(
        select(ServicePrincipal).where(ServicePrincipal.enrollment_id == enrollment.id)
    )
    if service is not None:
        principal = db.get(Principal, service.principal_id)
    return enrollment, invitation, principal


def decide_enrollment(
    db: Session,
    *,
    enrollment_id: int,
    approve: bool,
    actor_principal_id: int,
    fingerprint: str | None,
    note: str,
) -> AgentEnrollment:
    enrollment = db.get(AgentEnrollment, enrollment_id)
    if enrollment is None:
        raise AgentEnrollmentNotFound("enrollment not found")
    if enrollment.state != "pending":
        raise AgentEnrollmentConflict("enrollment is already terminal")
    if approve:
        if fingerprint != enrollment.fingerprint:
            raise AgentEnrollmentConflict("fingerprint confirmation required")
        invitation = db.get(AgentInvitation, enrollment.invitation_id)
        if invitation is None:
            raise AgentEnrollmentNotFound("invitation not found")
        reservation = db.get(AgentNamespaceReservation, invitation.reservation_id)
        if reservation is None or reservation.state != "reserved":
            raise AgentEnrollmentConflict("namespace reservation is unavailable")
        policy = json.loads(invitation.policy_json or "{}")
        now = utcnow()
        result = db.execute(
            update(AgentEnrollment)
            .where(AgentEnrollment.id == enrollment.id)
            .where(AgentEnrollment.state == "pending")
            .values(
                state="approved",
                decision_by_principal_id=actor_principal_id,
                decided_at=now,
                decision_note=note,
            )
        )
        changed = int(getattr(result, "rowcount", 0) or 0)
        if changed != 1:
            raise AgentEnrollmentConflict("enrollment was decided concurrently")
        principal = Principal(
            kind="service", slug=reservation.slug, display_name=reservation.display_name
        )
        db.add(principal)
        db.flush()
        service = ServicePrincipal(
            principal_id=principal.id,
            slug=reservation.slug,
            description=reservation.display_name,
            enrollment_id=enrollment.id,
            state="active",
            policy_json=json.dumps(policy, sort_keys=True),
            approved_at=now,
        )
        db.add(service)
        db.flush()
        reservation.state = "claimed"
        reservation.claimed_service_principal_id = service.id
        credential = Credential(
            principal_id=principal.id,
            type="agent_token",
            hashed_secret=enrollment.proposed_api_key_hash,
            scopes_json=identity_service.encode_scopes(
                {"agent:publish", "artifact:download", "release:read", "registry:publish"}
            ),
            resource_selector_json=json.dumps({"namespace_id": principal.id}, sort_keys=True),
            product_scope_type="namespace",
            product_scope_id=principal.id,
            product_token_type="publisher",  # noqa: S106
            product_token_name=f"agent:{reservation.slug}",
            created_at=now,
        )
        db.add(credential)
        return enrollment
    result = db.execute(
        update(AgentEnrollment)
        .where(AgentEnrollment.id == enrollment.id)
        .where(AgentEnrollment.state == "pending")
        .values(
            state="rejected",
            decision_by_principal_id=actor_principal_id,
            decided_at=utcnow(),
            decision_note=note,
        )
    )
    changed = int(getattr(result, "rowcount", 0) or 0)
    if changed != 1:
        raise AgentEnrollmentConflict("enrollment was decided concurrently")
    return enrollment


def list_enrollments(
    db: Session,
) -> list[tuple[AgentEnrollment, AgentInvitation, Principal | None]]:
    rows = db.scalars(select(AgentEnrollment).order_by(AgentEnrollment.created_at.asc())).all()
    output = []
    for row in rows:
        invitation = db.get(AgentInvitation, row.invitation_id)
        if invitation is None:
            continue
        service = db.scalar(
            select(ServicePrincipal).where(ServicePrincipal.enrollment_id == row.id)
        )
        principal = db.get(Principal, service.principal_id) if service is not None else None
        output.append((row, invitation, principal))
    return output
