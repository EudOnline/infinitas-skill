#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(command: list[str], *, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
        check=False,
    )
    if result.returncode != expect:
        fail(
            f"command {command!r} exited {result.returncode}, expected {expect}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
    os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["registry-reader-token"])
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(
        [
            {
                "username": "fixture-maintainer",
                "display_name": "Fixture Maintainer",
                "role": "maintainer",
                "token": "fixture-maintainer-token",
            }
        ]
    )


def insert_legacy_plaintext_user(db_path: Path, *, username: str, display_name: str, role: str, token: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users (username, display_name, role, token, light_bg_id, dark_bg_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (username, display_name, role, token),
        )
        conn.commit()


def scenario_access_credentials_and_release_scope() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-private-access-test-"))
    try:
        configure_env(tmpdir)
        run([sys.executable, "-m", "alembic", "upgrade", "20260329_0004"])
        insert_legacy_plaintext_user(
            tmpdir / "server.db",
            username="legacy-migrated",
            display_name="Legacy Migrated",
            role="contributor",
            token="legacy-migrated-token",
        )

        from fastapi.testclient import TestClient

        from server.app import create_app
        from server.db import get_session_factory
        from server.models import AccessGrant, Credential, Exposure, Principal, Release, Skill, SkillVersion, User
        from server.modules.access.service import hash_token

        client = TestClient(create_app())

        anonymous = client.get("/api/v1/access/me")
        if anonymous.status_code != 401:
            fail(f"expected anonymous /api/v1/access/me to return 401, got {anonymous.status_code}")

        migrated = client.get(
            "/api/v1/access/me",
            headers={"Authorization": "Bearer legacy-migrated-token"},
        )
        if migrated.status_code != 200:
            fail(
                "expected migrated plaintext user to authenticate after credential cutover, "
                f"got {migrated.status_code}: {migrated.text}"
            )
        migrated_payload = migrated.json()
        if migrated_payload.get("credential_type") != "personal_token":
            fail(f"expected migrated credential type personal_token, got {migrated_payload}")
        if migrated_payload.get("username") != "legacy-migrated":
            fail(f"expected migrated username legacy-migrated, got {migrated_payload}")

        me = client.get(
            "/api/v1/access/me",
            headers={"Authorization": "Bearer fixture-maintainer-token"},
        )
        if me.status_code != 200:
            fail(f"expected personal token access check to return 200, got {me.status_code}: {me.text}")
        me_payload = me.json()
        if me_payload.get("credential_type") != "personal_token":
            fail(f"expected personal_token credential type, got {me_payload}")
        if me_payload.get("username") != "fixture-maintainer":
            fail(f"expected fixture-maintainer username, got {me_payload}")

        session_factory = get_session_factory()
        with session_factory() as session:
            migrated_user = session.scalar(select(User).where(User.username == "legacy-migrated"))
            if migrated_user is None:
                fail("expected migrated user row to exist after cutover")
            if migrated_user.token is not None:
                fail("expected migrated user token to be scrubbed after credential cutover")

            migrated_principal = session.scalar(
                select(Principal).where(Principal.kind == "user").where(Principal.slug == "legacy-migrated")
            )
            if migrated_principal is None:
                fail("expected migrated user principal to be created during cutover")

            migrated_credential = session.scalar(
                select(Credential)
                .where(Credential.principal_id == migrated_principal.id)
                .where(Credential.type == "personal_token")
            )
            if migrated_credential is None:
                fail("expected migrated personal credential to exist after cutover")
            if migrated_credential.hashed_secret != hash_token("legacy-migrated-token"):
                fail("expected migrated personal credential to store a hashed secret")

            bootstrap_user = session.scalar(select(User).where(User.username == "fixture-maintainer"))
            if bootstrap_user is None:
                fail("expected bootstrap maintainer row to exist")
            if bootstrap_user.token is not None:
                fail("expected bootstrap personal token to live outside the users table")

            principal = session.scalar(
                select(Principal).where(Principal.kind == "user").where(Principal.slug == "fixture-maintainer")
            )
            if principal is None:
                fail("expected bridged user principal to exist")

            bootstrap_credential = session.scalar(
                select(Credential)
                .where(Credential.principal_id == principal.id)
                .where(Credential.type == "personal_token")
            )
            if bootstrap_credential is None:
                fail("expected bootstrap personal credential to exist")
            if bootstrap_credential.hashed_secret != hash_token("fixture-maintainer-token"):
                fail("expected bootstrap personal credential to store a hashed secret")

            skill = Skill(
                namespace_id=principal.id,
                slug="access-skill",
                display_name="Access Skill",
                summary="access test fixture",
                created_by_principal_id=principal.id,
            )
            session.add(skill)
            session.flush()

            grant_version = SkillVersion(
                skill_id=skill.id,
                version="0.1.0",
                content_digest="sha256:content-grant",
                metadata_digest="sha256:meta-grant",
                created_from_draft_id=None,
                created_by_principal_id=principal.id,
            )
            private_version = SkillVersion(
                skill_id=skill.id,
                version="0.2.0",
                content_digest="sha256:content-private",
                metadata_digest="sha256:meta-private",
                created_from_draft_id=None,
                created_by_principal_id=principal.id,
            )
            authenticated_version = SkillVersion(
                skill_id=skill.id,
                version="0.3.0",
                content_digest="sha256:content-authenticated",
                metadata_digest="sha256:meta-authenticated",
                created_from_draft_id=None,
                created_by_principal_id=principal.id,
            )
            session.add_all([grant_version, private_version, authenticated_version])
            session.flush()

            grant_release = Release(
                skill_version_id=grant_version.id,
                state="ready",
                created_by_principal_id=principal.id,
            )
            private_release = Release(
                skill_version_id=private_version.id,
                state="ready",
                created_by_principal_id=principal.id,
            )
            authenticated_release = Release(
                skill_version_id=authenticated_version.id,
                state="ready",
                created_by_principal_id=principal.id,
            )
            session.add_all([grant_release, private_release, authenticated_release])
            session.flush()

            grant_exposure = Exposure(
                release_id=grant_release.id,
                audience_type="grant",
                state="active",
                install_mode="enabled",
                requested_by_principal_id=principal.id,
            )
            private_exposure = Exposure(
                release_id=private_release.id,
                audience_type="private",
                state="active",
                install_mode="enabled",
                requested_by_principal_id=principal.id,
            )
            authenticated_exposure = Exposure(
                release_id=authenticated_release.id,
                audience_type="authenticated",
                state="active",
                install_mode="enabled",
                requested_by_principal_id=principal.id,
            )
            session.add_all([grant_exposure, private_exposure, authenticated_exposure])
            session.flush()

            grant = AccessGrant(
                exposure_id=grant_exposure.id,
                grant_type="link",
                subject_ref="g_tok_123",
                constraints_json="{}",
                state="active",
                created_by_principal_id=principal.id,
            )
            session.add(grant)
            session.flush()

            raw_grant_token = "grant-token-value"
            grant_credential = Credential(
                principal_id=None,
                grant_id=grant.id,
                type="grant_token",
                hashed_secret=hash_token(raw_grant_token),
                scopes_json='["artifact:download"]',
                resource_selector_json="{}",
            )
            service_principal = Principal(
                kind="service",
                slug="artifact-only-service",
                display_name="Artifact-Only Service",
            )
            session.add(service_principal)
            session.flush()
            service_credential = Credential(
                principal_id=service_principal.id,
                grant_id=None,
                type="service_token",
                hashed_secret=hash_token("artifact-only-service-token"),
                scopes_json='["artifact:download"]',
                resource_selector_json="{}",
            )
            session.add(grant_credential)
            session.add(service_credential)
            session.commit()

            grant_release_id = grant_release.id
            private_release_id = private_release.id
            authenticated_release_id = authenticated_release.id

        with session_factory() as session:
            session.add(
                User(
                    username="plaintext-only",
                    display_name="Plaintext Only",
                    role="contributor",
                    token="plaintext-only-token",
                )
            )
            session.commit()

        plaintext_only = client.get(
            "/api/v1/access/me",
            headers={"Authorization": "Bearer plaintext-only-token"},
        )
        if plaintext_only.status_code != 401:
            fail(
                "expected plaintext-only user records to be rejected after credential cutover, "
                f"got {plaintext_only.status_code}: {plaintext_only.text}"
            )

        grant_me = client.get(
            "/api/v1/access/me",
            headers={"Authorization": "Bearer grant-token-value"},
        )
        if grant_me.status_code != 200:
            fail(f"expected grant token /api/v1/access/me to return 200, got {grant_me.status_code}: {grant_me.text}")
        grant_payload = grant_me.json()
        if grant_payload.get("credential_type") != "grant_token":
            fail(f"expected grant_token credential type, got {grant_payload}")

        grant_allowed = client.get(
            f"/api/v1/access/releases/{grant_release_id}/check",
            headers={"Authorization": "Bearer grant-token-value"},
        )
        if grant_allowed.status_code != 200:
            fail(f"expected grant token to access granted release, got {grant_allowed.status_code}: {grant_allowed.text}")

        grant_denied = client.get(
            f"/api/v1/access/releases/{private_release_id}/check",
            headers={"Authorization": "Bearer grant-token-value"},
        )
        if grant_denied.status_code != 403:
            fail(
                "expected grant token to be denied for non-granted release, "
                f"got {grant_denied.status_code}: {grant_denied.text}"
            )

        authenticated_denied = client.get(
            f"/api/v1/access/releases/{authenticated_release_id}/check",
            headers={"Authorization": "Bearer artifact-only-service-token"},
        )
        if authenticated_denied.status_code != 403:
            fail(
                "expected non-user credential to be denied for authenticated audience, "
                f"got {authenticated_denied.status_code}: {authenticated_denied.text}"
            )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_access_credentials_and_release_scope()
    print("OK: private registry access api checks passed")


if __name__ == "__main__":
    main()
