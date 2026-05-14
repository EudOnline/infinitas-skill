"""Integration tests for GET /api/v1/profile/me endpoint."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _profile_client(tmp_path: Path) -> TestClient:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'profile.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "profile-test-secret"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"profile-tester","display_name":"Profile Tester",'
        '"role":"maintainer","token":"profile-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestProfileMeAuth:
    """Authentication requirements for /api/v1/profile/me."""

    def test_requires_authentication(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get("/api/v1/profile/me")
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_valid_token_returns_200(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        assert response.status_code == 200


class TestProfileMeIdentity:
    """Verify the identity section of the profile response."""

    def test_identity_fields(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        assert response.status_code == 200
        body = response.json()
        identity = body["identity"]

        assert "credential_id" in identity
        assert isinstance(identity["credential_id"], int)

        assert "credential_type" in identity
        assert identity["credential_type"] == "personal_token"

        assert "principal_id" in identity
        assert "principal_slug" in identity
        assert "principal_kind" in identity
        assert "principal_display_name" in identity
        assert identity["principal_slug"] == "profile-tester"
        assert identity["principal_kind"] == "user"
        assert identity["principal_display_name"] == "Profile Tester"

        assert "scopes" in identity
        assert isinstance(identity["scopes"], list)
        # Scopes must be sorted
        assert identity["scopes"] == sorted(identity["scopes"])

        assert "expires_at" in identity

    def test_scopes_are_sorted(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        body = response.json()
        scopes = body["identity"]["scopes"]
        assert scopes == sorted(scopes)


class TestProfileMeAccessibleSkills:
    """Verify the accessible_skills section."""

    def test_accessible_skills_is_list(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        body = response.json()
        assert "accessible_skills" in body
        assert isinstance(body["accessible_skills"], list)

    def test_accessible_skills_empty_when_no_grants(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        body = response.json()
        # Bootstrap user has personal_token, no grants
        assert body["accessible_skills"] == []


class TestProfileMeOperationHistory:
    """Verify the operation_history section."""

    def test_operation_history_is_list(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        body = response.json()
        assert "operation_history" in body
        assert isinstance(body["operation_history"], list)

    def test_operation_history_empty_when_no_events(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        body = response.json()
        assert body["operation_history"] == []

    def test_operation_history_returns_events_for_credential(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        # First, get the profile to know the credential_id
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        assert profile.status_code == 200
        cred_id = profile.json()["identity"]["credential_id"]

        # Insert audit events directly into the DB
        from server.db import get_session_factory
        from server.models import AuditEvent

        factory = get_session_factory()
        with factory() as session:
            for i in range(3):
                event = AuditEvent(
                    aggregate_type="credential",
                    aggregate_id=str(cred_id),
                    event_type=f"test.event.{i}",
                    actor_ref=f"credential:{cred_id}",
                    payload_json=json.dumps({"index": i}),
                    occurred_at=datetime.now(timezone.utc),
                )
                session.add(event)
            session.commit()

        # Now fetch profile again
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        assert response.status_code == 200
        history = response.json()["operation_history"]
        assert len(history) == 3
        event_types = {h["event_type"] for h in history}
        assert "test.event.0" in event_types
        assert "test.event.1" in event_types
        assert "test.event.2" in event_types

    def test_operation_history_limited_to_50(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        from server.db import get_session_factory
        from server.models import AuditEvent

        factory = get_session_factory()
        with factory() as session:
            for i in range(60):
                event = AuditEvent(
                    aggregate_type="credential",
                    aggregate_id=str(cred_id),
                    event_type=f"bulk.event.{i}",
                    actor_ref=f"credential:{cred_id}",
                    payload_json=json.dumps({"i": i}),
                    occurred_at=datetime.now(timezone.utc) - timedelta(seconds=60 - i),
                )
                session.add(event)
            session.commit()

        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        history = response.json()["operation_history"]
        assert len(history) == 50

    def test_operation_history_excludes_other_credentials(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        from server.db import get_session_factory
        from server.models import AuditEvent

        factory = get_session_factory()
        with factory() as session:
            # Event for a different credential ID
            event = AuditEvent(
                aggregate_type="credential",
                aggregate_id=str(cred_id + 9999),
                event_type="other.credential.event",
                actor_ref="credential:9999",
                payload_json="{}",
                occurred_at=datetime.now(timezone.utc),
            )
            session.add(event)
            session.commit()

        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        history = response.json()["operation_history"]
        assert len(history) == 0


class TestProfileMePolicy:
    """Verify the policy section."""

    def test_policy_is_none_when_no_grant(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        body = response.json()
        # Personal token has no associated grant, so policy should be None
        assert body["policy"] is None

    def test_policy_returns_constraints_from_grant(self, tmp_path: Path):
        client = _profile_client(tmp_path)

        # Get the current profile to find the principal
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        principal_id = profile.json()["identity"]["principal_id"]

        from server.db import get_session_factory
        from server.models import (
            AccessGrant,
            Credential,
            Exposure,
            Principal,
            RegistryObject,
            Release,
            SkillVersion,
        )

        factory = get_session_factory()
        with factory() as session:
            # Create a RegistryObject, SkillVersion, Release, Exposure chain
            namespace = Principal(
                kind="user",
                slug="grant-tester-ns",
                display_name="Grant Tester NS",
            )
            session.add(namespace)
            session.flush()

            obj = RegistryObject(
                kind="skill",
                namespace_id=namespace.id,
                slug="test-skill-for-grant",
                display_name="Test Skill For Grant",
            )
            session.add(obj)
            session.flush()

            sv = SkillVersion(
                skill_id=obj.id,
                version="1.0.0",
                content_digest="abc",
                metadata_digest="def",
            )
            session.add(sv)
            session.flush()

            release = Release(
                skill_version_id=sv.id,
                registry_object_id=obj.id,
                state="ready",
            )
            session.add(release)
            session.flush()

            exposure = Exposure(
                release_id=release.id,
                audience_type="grant",
                state="active",
                install_mode="enabled",
            )
            session.add(exposure)
            session.flush()

            # Create AccessGrant
            constraints = json.dumps({"max_downloads": 10, "regions": ["us"]})
            grant = AccessGrant(
                exposure_id=exposure.id,
                grant_type="token",
                subject_ref=f"principal:{principal_id}",
                constraints_json=constraints,
                state="active",
            )
            session.add(grant)
            session.flush()

            # Create a credential linked to this grant
            from server.modules.access.service import hash_token

            raw = "grant_test_token_for_policy"
            cred = Credential(
                principal_id=principal_id,
                grant_id=grant.id,
                type="grant_token",
                hashed_secret=hash_token(raw),
                scopes_json='["artifact:download"]',
                resource_selector_json="{}",
            )
            session.add(cred)
            session.commit()

        # Use the grant token to authenticate
        response = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert response.status_code == 200
        body = response.json()
        policy = body["policy"]
        assert policy is not None
        assert policy["max_downloads"] == 10
        assert policy["regions"] == ["us"]

        # Should also see accessible_skills populated
        skills = body["accessible_skills"]
        assert isinstance(skills, list)
        assert len(skills) >= 1
        # Check that our skill is in the list
        slugs = {s["slug"] for s in skills}
        assert "test-skill-for-grant" in slugs
