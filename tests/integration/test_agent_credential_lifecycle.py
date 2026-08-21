from __future__ import annotations

import secrets
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from infinitas_skill.agent.profile import fingerprint, verifier
from server.model_base import utcnow
from server.modules.audit.models import AuditEvent
from server.modules.identity.models import (
    AgentEnrollment,
    AgentInvitation,
    AgentNamespaceReservation,
    Credential,
    Principal,
    ServicePrincipal,
)
from tests.integration.test_agent_enrollment_public_backup import (
    _client,
    _enroll_and_approve,
)


def _db_rows() -> tuple[ServicePrincipal, Principal, int]:
    from server.db import get_session_factory

    with get_session_factory()() as db:
        service = db.scalar(
            select(ServicePrincipal).where(ServicePrincipal.enrollment_id.is_not(None))
        )
        assert service is not None
        principal = db.get(Principal, service.principal_id)
        assert principal is not None
        actor_id = db.scalar(
            select(AgentInvitation.created_by_principal_id).order_by(AgentInvitation.id).limit(1)
        )
        assert actor_id is not None
        return service, principal, int(actor_id)


def test_suspend_resume_and_permanent_revoke_gate_all_agent_credentials(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    headers = _enroll_and_approve(client)
    service, principal, actor_id = _db_rows()
    from server.db import get_session_factory
    from server.modules.identity import agent_lifecycle

    with get_session_factory()() as db:
        agent_lifecycle.transition_agent(
            db, service_id=service.id, action="suspend", actor_principal_id=actor_id
        )
        db.commit()
    assert client.get("/api/v1/access/me", headers=headers).status_code == 401

    with get_session_factory()() as db:
        agent_lifecycle.transition_agent(
            db, service_id=service.id, action="resume", actor_principal_id=actor_id
        )
        db.commit()
    assert client.get("/api/v1/access/me", headers=headers).status_code == 200

    with get_session_factory()() as db:
        agent_lifecycle.transition_agent(
            db, service_id=service.id, action="revoke", actor_principal_id=actor_id
        )
        db.commit()
    assert client.get("/api/v1/access/me", headers=headers).status_code == 401
    with get_session_factory()() as db:
        revoked = db.get(ServicePrincipal, service.id)
        assert revoked is not None and revoked.state == "revoked"
        assert not db.scalars(
            select(Credential).where(
                Credential.principal_id == principal.id,
                Credential.type == "agent_token",
                Credential.revoked_at.is_(None),
            )
        ).all()
        events = set(
            db.scalars(select(AuditEvent.event_type).where(AuditEvent.aggregate_type == "agent"))
        )
        assert {"agent.suspended", "agent.active", "agent.revoked"} <= events


def test_self_rotation_is_atomic_and_preserves_policy_scope(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    headers = _enroll_and_approve(client)
    new_key = "agt_" + secrets.token_urlsafe(32)
    replacement_verifier = verifier(new_key)

    rotated = client.post(
        "/api/v1/agent/credentials/rotate",
        headers=headers,
        json={
            "api_key_verifier": replacement_verifier,
            "fingerprint": fingerprint(replacement_verifier),
        },
    )

    assert rotated.status_code == 200, rotated.text
    assert client.get("/api/v1/access/me", headers=headers).status_code == 401
    replacement_headers = {"Authorization": f"Bearer {new_key}"}
    identity = client.get("/api/v1/access/me", headers=replacement_headers)
    assert identity.status_code == 200
    assert "agent:publish" in identity.json()["scopes"]


def test_concurrent_self_rotation_cas_leaves_one_active_replacement(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    _enroll_and_approve(client)
    from server.db import get_session_factory
    from server.modules.identity import agent_lifecycle
    from server.modules.identity.agent_service import AgentEnrollmentConflict

    factory = get_session_factory()
    first = factory()
    stale = factory()
    try:
        first_credential = first.scalar(
            select(Credential).where(
                Credential.type == "agent_token", Credential.revoked_at.is_(None)
            )
        )
        stale_credential = stale.scalar(
            select(Credential).where(
                Credential.type == "agent_token", Credential.revoked_at.is_(None)
            )
        )
        assert first_credential is not None and stale_credential is not None
        principal = first.get(Principal, first_credential.principal_id)
        stale_principal = stale.get(Principal, stale_credential.principal_id)
        assert principal is not None and stale_principal is not None
        first_verifier = verifier("agt_first-replacement")
        agent_lifecycle.rotate_agent_credential(
            first,
            current_credential=first_credential,
            principal=principal,
            api_key_verifier=first_verifier,
            fingerprint=fingerprint(first_verifier),
            request_id="rotation-first",
        )
        first.commit()

        stale_verifier = verifier("agt_stale-replacement")
        with pytest.raises(AgentEnrollmentConflict, match="concurrently"):
            agent_lifecycle.rotate_agent_credential(
                stale,
                current_credential=stale_credential,
                principal=stale_principal,
                api_key_verifier=stale_verifier,
                fingerprint=fingerprint(stale_verifier),
                request_id="rotation-stale",
            )
        stale.rollback()
    finally:
        first.close()
        stale.close()

    with factory() as db:
        active = db.scalars(
            select(Credential).where(
                Credential.type == "agent_token", Credential.revoked_at.is_(None)
            )
        ).all()
        assert len(active) == 1
        assert active[0].hashed_secret == first_verifier


def test_recovery_replaces_credentials_without_creating_another_principal(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    old_headers = _enroll_and_approve(client)
    service, principal, actor_id = _db_rows()
    from server.db import get_session_factory
    from server.modules.identity import agent_lifecycle, agent_service

    with get_session_factory()() as db:
        principal_count = int(db.scalar(select(func.count()).select_from(Principal)) or 0)
        invitation, raw, _prompt = agent_lifecycle.create_recovery_invitation(
            db,
            service_id=service.id,
            request_nonce=agent_service.new_invitation_request_nonce(),
            expires_in_minutes=30,
            actor_principal_id=actor_id,
            base_url="http://testserver",
        )
        recovery_invitation_id = invitation.id
        db.commit()

    status_key = "status_" + secrets.token_urlsafe(32)
    new_key = "agt_" + secrets.token_urlsafe(32)
    api_verifier = verifier(new_key)
    submitted = client.post(
        "/api/v1/agent-enrollments",
        headers={"Authorization": f"Bearer {raw}"},
        json={
            "status_verifier": verifier(status_key),
            "api_key_verifier": api_verifier,
            "fingerprint": fingerprint(api_verifier),
        },
    )
    assert submitted.status_code == 201, submitted.text
    with get_session_factory()() as db:
        enrollment = db.scalar(
            select(AgentEnrollment).where(AgentEnrollment.invitation_id == recovery_invitation_id)
        )
        assert enrollment is not None
        agent_service.decide_enrollment(
            db,
            enrollment_id=enrollment.id,
            approve=True,
            actor_principal_id=actor_id,
            enrollment_public_id=enrollment.public_id,
            fingerprint=enrollment.fingerprint,
            note="approved recovery",
        )
        db.commit()

    assert client.get("/api/v1/access/me", headers=old_headers).status_code == 401
    recovered = client.get("/api/v1/access/me", headers={"Authorization": f"Bearer {new_key}"})
    assert recovered.status_code == 200
    assert recovered.json()["principal_id"] == principal.id
    with get_session_factory()() as db:
        assert int(db.scalar(select(func.count()).select_from(Principal)) or 0) == principal_count


def test_recovery_invitation_replaces_expired_open_invitation(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    _enroll_and_approve(client)
    service, _principal, actor_id = _db_rows()
    from server.db import get_session_factory
    from server.modules.identity import agent_lifecycle, agent_service

    with get_session_factory()() as db:
        first, _raw, _prompt = agent_lifecycle.create_recovery_invitation(
            db,
            service_id=service.id,
            request_nonce=agent_service.new_invitation_request_nonce(),
            expires_in_minutes=30,
            actor_principal_id=actor_id,
            base_url="http://testserver",
        )
        first_id = first.id
        first.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()

    with get_session_factory()() as db:
        replacement, _raw, _prompt = agent_lifecycle.create_recovery_invitation(
            db,
            service_id=service.id,
            request_nonce=agent_service.new_invitation_request_nonce(),
            expires_in_minutes=30,
            actor_principal_id=actor_id,
            base_url="http://testserver",
        )
        replacement_id = replacement.id
        db.commit()

    with get_session_factory()() as db:
        expired = db.get(AgentInvitation, first_id)
        replacement = db.get(AgentInvitation, replacement_id)
        assert expired is not None and expired.state == "expired"
        assert replacement is not None and replacement.state == "open"


def test_invitation_revoke_then_unclaimed_reservation_release(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    from server.db import get_session_factory
    from server.modules.identity import agent_lifecycle, agent_service
    from server.modules.identity import service as identity_service
    from server.modules.identity.models import User

    with get_session_factory()() as db:
        user = db.scalar(select(User).where(User.username == "fixture-maintainer"))
        assert user is not None
        actor = identity_service.ensure_user_principal(db, user)
        invitation, _raw, _prompt = agent_service.create_invitation(
            db,
            slug="releasable-agent",
            request_nonce=agent_service.new_invitation_request_nonce(),
            display_name="Releasable Agent",
            expires_in_minutes=30,
            max_daily_publishes=3,
            auto_public_publish=True,
            creator_principal_id=actor.id,
            base_url="http://testserver",
        )
        reservation_id = invitation.reservation_id
        agent_lifecycle.revoke_invitation(
            db, invitation_id=invitation.id, actor_principal_id=actor.id
        )
        agent_lifecycle.release_reservation(
            db, reservation_id=reservation_id, actor_principal_id=actor.id
        )
        db.commit()
    with get_session_factory()() as db:
        reservation = db.get(AgentNamespaceReservation, reservation_id)
        assert reservation is not None and reservation.state == "released"
