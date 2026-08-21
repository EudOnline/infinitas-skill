from __future__ import annotations

import argparse
import json
import re
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from infinitas_skill.agent.profile import fingerprint, verifier
from server.model_base import utcnow
from server.modules.identity.models import AgentEnrollment, AgentInvitation, User
from server.modules.release.models import AgentPublishIntent
from tests.helpers.hosted_content import upload_skill_content
from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)


@contextmanager
def _live_server():
    import uvicorn

    from server.app import create_app

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = int(probe.getsockname()[1])
    probe.close()
    address = f"http://127.0.0.1:{port}"
    instance = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=instance.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while True:
        if time.monotonic() >= deadline or not thread.is_alive():
            raise RuntimeError("integration HTTP server did not become ready")
        try:
            with urllib.request.urlopen(f"{address}/api/v1/system/healthz", timeout=1) as response:
                if response.status == 200:
                    break
        except (OSError, urllib.error.URLError):
            time.sleep(0.05)
    try:
        yield address
    finally:
        instance.should_exit = True
        thread.join(timeout=10)
        if thread.is_alive():
            raise RuntimeError("integration HTTP server did not stop")


def _client(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> TestClient:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    from server.app import create_app

    return TestClient(create_app())


def _create_invitation(*, max_daily_publishes: int = 3) -> tuple[str, int]:
    from server.db import get_session_factory
    from server.modules.identity import agent_service
    from server.modules.identity import service as identity_service

    with get_session_factory()() as db:
        user = db.scalar(select(User).where(User.username == "fixture-maintainer"))
        assert user is not None
        actor = identity_service.ensure_user_principal(db, user)
        _invitation, raw, _prompt = agent_service.create_invitation(
            db,
            slug="backup-agent",
            request_nonce=agent_service.new_invitation_request_nonce(),
            display_name="Backup Agent",
            expires_in_minutes=30,
            max_daily_publishes=max_daily_publishes,
            auto_public_publish=True,
            creator_principal_id=actor.id,
            base_url="http://testserver",
        )
        db.commit()
        return raw, actor.id


def _enroll_and_approve(client: TestClient, *, max_daily_publishes: int = 3) -> dict[str, str]:
    from server.db import get_session_factory
    from server.modules.identity import agent_service

    invitation, actor_id = _create_invitation(max_daily_publishes=max_daily_publishes)
    status_key = "status_" + secrets.token_urlsafe(32)
    api_key = "agt_" + secrets.token_urlsafe(32)
    api_verifier = verifier(api_key)
    submitted = client.post(
        "/api/v1/agent-enrollments",
        headers={"Authorization": f"Bearer {invitation}"},
        json={
            "status_verifier": verifier(status_key),
            "api_key_verifier": api_verifier,
            "fingerprint": fingerprint(api_verifier),
            "runtime": {"platform": "test", "cli_version": "1"},
        },
    )
    assert submitted.status_code == 201, submitted.text
    with get_session_factory()() as db:
        enrollment = db.scalar(
            select(AgentEnrollment).where(
                AgentEnrollment.public_id == submitted.json()["public_id"]
            )
        )
        assert enrollment is not None
        agent_service.decide_enrollment(
            db,
            enrollment_id=enrollment.id,
            approve=True,
            actor_principal_id=actor_id,
            enrollment_public_id=enrollment.public_id,
            fingerprint=enrollment.fingerprint,
            note="approved by integration test",
        )
        db.commit()
    status = client.get(
        f"/api/v1/agent-enrollments/{submitted.json()['public_id']}",
        headers={"Authorization": f"Bearer {status_key}"},
    )
    assert status.status_code == 200, status.text
    assert status.json()["state"] == "approved"
    return {"Authorization": f"Bearer {api_key}"}


def _create_agent_version(
    client: TestClient,
    headers: dict[str, str],
    *,
    version: str,
) -> tuple[int, int]:
    skills = client.get("/api/v1/skills?slug=public-backup", headers=headers)
    assert skills.status_code == 200, skills.text
    if skills.json():
        skill_id = int(skills.json()[0]["id"])
    else:
        created = client.post(
            "/api/v1/skills",
            headers=headers,
            json={
                "slug": "public-backup",
                "display_name": "Public Backup",
                "summary": "Agent public backup acceptance fixture",
            },
        )
        assert created.status_code == 201, created.text
        skill_id = int(created.json()["id"])
    content = upload_skill_content(
        client,
        skill_id,
        "public-backup",
        version,
        headers,
        publisher="backup-agent",
    )
    created_version = client.post(
        f"/api/v1/skills/{skill_id}/versions",
        headers=headers,
        json={"version": version, "content_id": content["content_id"]},
    )
    assert created_version.status_code == 201, created_version.text
    return skill_id, int(created_version.json()["id"])


def test_agent_enrollment_publish_wait_contract_and_anonymous_public_read(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    headers = _enroll_and_approve(client)
    identity = client.get("/api/v1/access/me", headers=headers)
    assert identity.status_code == 200
    assert identity.json()["principal_slug"] == "backup-agent"
    assert "release:read" in identity.json()["scopes"]

    _skill_id, version_id = _create_agent_version(client, headers, version="1.0.0")
    published = client.post(f"/api/v1/agent/versions/{version_id}/publish", headers=headers)
    assert published.status_code == 202, published.text
    release_id = int(published.json()["id"])

    from server.worker import run_worker_loop

    assert run_worker_loop(limit=1) == 1
    release = client.get(f"/api/v1/releases/{release_id}", headers=headers)
    assert release.status_code == 200, release.text
    assert release.json()["state"] == "ready"
    publish_status = client.get(f"/api/v1/agent/publish-intents/{release_id}", headers=headers)
    assert publish_status.status_code == 200, publish_status.text
    assert publish_status.json()["state"] == "activated"
    assert publish_status.json()["release_state"] == "ready"

    anonymous = client.get("/api/v1/registry/distributions.json")
    assert anonymous.status_code == 200, anonymous.text
    entry = next(
        item
        for item in anonymous.json()["skills"]
        if item["qualified_name"] == "backup-agent/public-backup"
    )
    assert entry["audience_type"] == "public"
    assert entry["listing_mode"] == "listed"


def test_agent_publish_quota_returns_429_with_retry_after(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    headers = _enroll_and_approve(client, max_daily_publishes=1)
    _skill_id, first_version = _create_agent_version(client, headers, version="1.0.0")
    first = client.post(f"/api/v1/agent/versions/{first_version}/publish", headers=headers)
    assert first.status_code == 202, first.text
    _skill_id, second_version = _create_agent_version(client, headers, version="1.1.0")

    limited = client.post(f"/api/v1/agent/versions/{second_version}/publish", headers=headers)

    assert limited.status_code == 429, limited.text
    assert int(limited.headers["Retry-After"]) > 0
    from server.db import get_session_factory

    with get_session_factory()() as db:
        assert db.scalar(select(AgentPublishIntent).where(AgentPublishIntent.id > 1)) is None


def test_agent_publish_requires_explicit_agent_publish_scope(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    headers = _enroll_and_approve(client)
    _skill_id, version_id = _create_agent_version(client, headers, version="1.0.0")
    from server.db import get_session_factory
    from server.modules.identity import service as identity_service
    from server.modules.identity.models import Credential

    with get_session_factory()() as db:
        credential = db.scalar(select(Credential).where(Credential.type == "agent_token"))
        assert credential is not None
        credential.scopes_json = identity_service.encode_scopes(
            {"release:read", "registry:publish"}
        )
        db.commit()

    denied = client.post(f"/api/v1/agent/versions/{version_id}/publish", headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "agent publish scope required"


def test_agent_admin_form_handles_invalid_numbers_and_replayed_nonce(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    from server.db import get_session_factory
    from server.modules.identity import service as identity_service
    from server.modules.identity.auth import AUTH_COOKIE_NAME, create_auth_session_cookie

    with get_session_factory()() as db:
        user = db.scalar(select(User).where(User.username == "fixture-maintainer"))
        assert user is not None
        principal = identity_service.ensure_user_principal(db, user)
        credential = identity_service.create_fresh_session_credential(db, principal_id=principal.id)
        db.commit()
    client.cookies.set(AUTH_COOKIE_NAME, create_auth_session_cookie(credential.id))
    client.cookies.set("csrf_token", "agent-form-csrf")
    page = client.get("/agents")
    nonce = re.search(r'name="request_nonce" value="([^"]+)"', page.text)
    assert nonce is not None
    common = {
        "request_nonce": nonce.group(1),
        "slug": "form-agent",
        "display_name": "Form Agent",
        "max_daily_publishes": "100",
        "auto_public_publish": "true",
    }
    request_headers = {"X-CSRF-Token": "agent-form-csrf"}
    invalid = client.post(
        "/agents/invitations",
        headers=request_headers,
        data={**common, "expires_in_minutes": "not-a-number"},
    )
    assert invalid.status_code == 422
    assert 'role="alert"' in invalid.text
    assert "not-a-number" in invalid.text

    valid = client.post(
        "/agents/invitations",
        headers=request_headers,
        data={**common, "expires_in_minutes": "30"},
    )
    assert valid.status_code == 200
    replay = client.post(
        "/agents/invitations",
        headers=request_headers,
        data={**common, "expires_in_minutes": "30"},
    )
    assert replay.status_code == 409
    assert "Invitation token (paste into stdin only)" not in replay.text

    forged = client.post(
        "/agents/invitations",
        headers=request_headers,
        data={
            **common,
            "request_nonce": "ainr_" + "a" * 32 + "." + "b" * 43,
            "slug": "forged-agent",
            "expires_in_minutes": "30",
        },
    )
    assert forged.status_code == 409
    assert "invalid invitation request nonce" in forged.text


def test_agent_approval_requires_public_id_and_fingerprint_confirmation(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    invitation, actor_id = _create_invitation()
    status_key = "status_" + secrets.token_urlsafe(32)
    api_key = "agt_" + secrets.token_urlsafe(32)
    api_verifier = verifier(api_key)
    submitted = client.post(
        "/api/v1/agent-enrollments",
        headers={"Authorization": f"Bearer {invitation}"},
        json={
            "status_verifier": verifier(status_key),
            "api_key_verifier": api_verifier,
            "fingerprint": fingerprint(api_verifier),
        },
    )
    assert submitted.status_code == 201
    from server.db import get_session_factory
    from server.modules.identity import agent_service

    with get_session_factory()() as db:
        enrollment = db.scalar(select(AgentEnrollment))
        assert enrollment is not None
        for public_id, candidate_fingerprint in (
            ("aenr_wrong", enrollment.fingerprint),
            (enrollment.public_id, "0" * 16),
        ):
            try:
                agent_service.decide_enrollment(
                    db,
                    enrollment_id=enrollment.id,
                    approve=True,
                    actor_principal_id=actor_id,
                    enrollment_public_id=public_id,
                    fingerprint=candidate_fingerprint,
                    note="",
                )
            except agent_service.AgentEnrollmentConflict:
                db.rollback()
            else:
                raise AssertionError("approval accepted an identity mismatch")


def test_expired_enrollment_invitation_returns_410_and_persists_state(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    invitation, _actor_id = _create_invitation()
    from server.db import get_session_factory

    with get_session_factory()() as db:
        row = db.scalar(select(AgentInvitation))
        assert row is not None
        invitation_id = row.id
        row.expires_at = utcnow() - timedelta(minutes=1)
        db.commit()

    response = client.post(
        "/api/v1/agent-enrollments",
        headers={"Authorization": f"Bearer {invitation}"},
        json={
            "status_verifier": "sha256:" + "a" * 64,
            "api_key_verifier": "sha256:" + "b" * 64,
            "fingerprint": "c" * 16,
        },
    )

    assert response.status_code == 410
    assert response.json()["detail"] == "invitation has expired"
    with get_session_factory()() as db:
        row = db.get(AgentInvitation, invitation_id)
        assert row is not None and row.state == "expired"


def test_invitation_result_uses_external_csp_compatible_copy_handler(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    template = Path("server/templates/agent-invitation-created.html").read_text(encoding="utf-8")
    assert "<script>" not in template
    assert "static/js/modules/agents.js" in template
    assert 'role="status"' in template
    source = Path("server/static/js/modules/agents.js").read_text(encoding="utf-8")
    assert "navigator.clipboard.writeText" in source


def test_database_rejects_second_open_invitation_for_reservation(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    _raw, _actor_id = _create_invitation()
    from server.db import get_session_factory

    with get_session_factory()() as db:
        existing = db.scalar(select(AgentInvitation))
        assert existing is not None
        duplicate = AgentInvitation(
            public_id="ainv_duplicate-open",
            reservation_id=existing.reservation_id,
            purpose="enroll",
            invitation_hash="sha256:" + "a" * 64,
            request_nonce_hash="sha256:" + "b" * 64,
            policy_json=json.dumps({}),
            state="open",
            expires_at=existing.expires_at,
            created_by_principal_id=existing.created_by_principal_id,
        )
        db.add(duplicate)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
        else:
            raise AssertionError("database accepted two open invitations for one reservation")


def test_anonymous_agent_restore_verify_update_and_rollback_use_trusted_installer(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _client(monkeypatch, tmp_path, temp_repo_copy, signing_key)
    headers = _enroll_and_approve(client)
    from infinitas_skill.agent import cli as agent_cli
    from infinitas_skill.install.install_manifest import load_install_manifest
    from infinitas_skill.install.rollback import run_install_rollback
    from server.worker import run_worker_loop

    for version in ("1.9.0", "1.10.0"):
        _skill_id, version_id = _create_agent_version(client, headers, version=version)
        published = client.post(f"/api/v1/agent/versions/{version_id}/publish", headers=headers)
        assert published.status_code == 202, published.text
        assert run_worker_loop(limit=1) == 1

    target = tmp_path / "anonymous-install"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "missing-profile-root"))
    with _live_server() as base_url:
        restore_args = argparse.Namespace(
            base_url=base_url,
            profile="missing",
            registry="public",
            qualified_name="backup-agent/public-backup",
            version="1.9.0",
            target=str(target),
            force=False,
        )
        assert agent_cli._restore(restore_args) == 0
        manifest = load_install_manifest(target)
        current = manifest["skills"]["public-backup"]
        assert current["installed_version"] == "1.9.0"
        assert current["source_trust"] == "public"

        assert (
            agent_cli._verify(
                argparse.Namespace(target=str(target), qualified_name="backup-agent/public-backup")
            )
            == 0
        )
        assert (
            agent_cli._update(
                argparse.Namespace(
                    target=str(target),
                    qualified_name="backup-agent/public-backup",
                    base_url=base_url,
                    registry="public",
                    profile="missing",
                    force=True,
                )
            )
            == 0
        )
        manifest = load_install_manifest(target)
        current = manifest["skills"]["public-backup"]
        assert current["installed_version"] == "1.10.0"
        assert manifest["history"]["public-backup"][-1]["installed_version"] == "1.9.0"

        assert (
            run_install_rollback(
                root=target,
                installed_name="backup-agent/public-backup",
                target_dir=str(target),
                force=True,
                as_json=True,
            )
            == 0
        )
        rolled_back = load_install_manifest(target)
        assert rolled_back["skills"]["public-backup"]["installed_version"] == "1.9.0"
