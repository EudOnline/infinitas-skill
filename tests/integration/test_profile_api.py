"""Integration tests for Profile API endpoints."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _profile_client(tmp_path: Path) -> TestClient:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'profile.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "profile-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"profile-tester","display_name":"Profile Tester",'
        '"role":"maintainer","token":"profile-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


def _contributor_client(tmp_path: Path) -> TestClient:
    """Create a client with a contributor-role user."""
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'profile.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "profile-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"contrib-user","display_name":"Contrib User",'
        '"role":"contributor","token":"contrib-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


def _viewer_client(tmp_path: Path) -> TestClient:
    """Create a client with a viewer-role user (no admin access)."""
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'profile.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "profile-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"viewer-user","display_name":"Viewer User",'
        '"role":"viewer","token":"viewer-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/v1/profile/me  (existing tests)
# ═══════════════════════════════════════════════════════════════════════════════


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
        from server.modules.audit.models import AuditEvent

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
        from server.modules.audit.models import AuditEvent

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
        from server.modules.audit.models import AuditEvent

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
        from server.modules.access.models import AccessGrant
        from server.modules.authoring.models import Skill, SkillContent, SkillVersion
        from server.modules.exposure.models import Exposure
        from server.modules.identity.models import Credential, Principal
        from server.modules.release.models import Release

        factory = get_session_factory()
        with factory() as session:
            # Create a Skill, SkillVersion, Release, Exposure chain
            namespace = Principal(
                kind="user",
                slug="grant-tester-ns",
                display_name="Grant Tester NS",
            )
            session.add(namespace)
            session.flush()

            skill = Skill(
                namespace_id=namespace.id,
                slug="test-skill-for-grant",
                display_name="Test Skill For Grant",
            )
            session.add(skill)
            session.flush()

            content = SkillContent(
                public_id="cnt_profilegrantfixture",
                skill_id=skill.id,
                storage_uri="objects/sha256/profile-grant",
                sha256="a" * 64,
                size_bytes=1,
                declared_version="1.0.0",
                state="consumed",
                created_by_principal_id=namespace.id,
            )
            session.add(content)
            session.flush()
            sv = SkillVersion(
                skill_id=skill.id,
                content_id=content.id,
                version="1.0.0",
                content_digest="abc",
                metadata_digest="def",
            )
            session.add(sv)
            session.flush()

            release = Release(
                skill_version_id=sv.id,
                skill_id=skill.id,
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
            from server.modules.identity.service import hash_token

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


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2: GET /api/v1/profile/{credential_id} — Admin View
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfileAdminViewAuth:
    """Authentication and authorization for admin view endpoint."""

    def test_requires_authentication(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get("/api/v1/profile/1")
        assert response.status_code == 401

    def test_maintainer_role_allowed(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        # Get own credential id first
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        response = client.get(
            f"/api/v1/profile/{cred_id}",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        assert response.status_code == 200

    def test_contributor_role_allowed(self, tmp_path: Path):
        client = _contributor_client(tmp_path)
        # Get own credential id first
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer contrib-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        response = client.get(
            f"/api/v1/profile/{cred_id}",
            headers={"Authorization": "Bearer contrib-test-token"},
        )
        assert response.status_code == 200

    def test_contributor_cannot_update_another_principals_credential(self, tmp_path: Path):
        client = _contributor_client(tmp_path)

        from server.db import get_session_factory
        from server.modules.identity.models import Credential, Principal

        with get_session_factory()() as session:
            other = Principal(kind="user", slug="other-policy-user", display_name="Other")
            session.add(other)
            session.flush()
            credential = Credential(
                principal_id=other.id,
                type="personal_token",
                hashed_secret="sha256:other",
            )
            session.add(credential)
            session.commit()
            credential_id = credential.id

        response = client.patch(
            f"/api/v1/credentials/{credential_id}/policy",
            headers={"Authorization": "Bearer contrib-test-token"},
            json={"readonly": True},
        )

        assert response.status_code == 403

    def test_viewer_role_forbidden(self, tmp_path: Path):
        client = _viewer_client(tmp_path)
        response = client.get(
            "/api/v1/profile/1",
            headers={"Authorization": "Bearer viewer-test-token"},
        )
        assert response.status_code == 403

    def test_invalid_token_returns_401(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/1",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401


class TestProfileAdminViewData:
    """Data returned by the admin view endpoint."""

    def test_returns_same_structure_as_me(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        # Get profile via /me
        me = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = me.json()["identity"]["credential_id"]

        # Get same profile via admin view
        admin = client.get(
            f"/api/v1/profile/{cred_id}",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        assert admin.status_code == 200
        body = admin.json()

        # Must have same top-level keys
        assert "identity" in body
        assert "accessible_skills" in body
        assert "operation_history" in body
        assert "policy" in body

        # Identity should match
        assert body["identity"]["credential_id"] == cred_id
        assert body["identity"]["principal_slug"] == "profile-tester"

    def test_returns_404_for_nonexistent_credential(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.get(
            "/api/v1/profile/99999",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        assert response.status_code == 404

    def test_can_view_other_credential(self, tmp_path: Path):
        """A maintainer can view another credential's profile."""
        client = _profile_client(tmp_path)
        # Create a second user and credential via DB
        from server.db import get_session_factory
        from server.modules.identity.models import Credential, Principal, User
        from server.modules.identity.service import hash_token

        factory = get_session_factory()
        with factory() as session:
            user = User(
                username="other-user",
                display_name="Other User",
                role="contributor",
            )
            session.add(user)
            session.flush()

            principal = Principal(
                kind="user",
                slug="other-user",
                display_name="Other User",
            )
            session.add(principal)
            session.flush()

            raw = "other-user-token"
            cred = Credential(
                principal_id=principal.id,
                type="personal_token",
                hashed_secret=hash_token(raw),
                scopes_json='["api:user"]',
                resource_selector_json="{}",
            )
            session.add(cred)
            session.commit()
            other_cred_id = cred.id

        # Maintainer views the other credential's profile
        response = client.get(
            f"/api/v1/profile/{other_cred_id}",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["identity"]["credential_id"] == other_cred_id
        assert body["identity"]["principal_slug"] == "other-user"


# ═══════════════════════════════════════════════════════════════════════════════
# Task 3: PATCH /api/v1/credentials/{credential_id}/policy
# ═══════════════════════════════════════════════════════════════════════════════


class TestCredentialPolicyUpdateAuth:
    """Authentication and authorization for the policy update endpoint."""

    def test_requires_authentication(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.patch(
            "/api/v1/credentials/1/policy",
            json={"readonly": True},
        )
        assert response.status_code == 401

    def test_maintainer_role_allowed(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"readonly": True},
        )
        assert response.status_code == 200

    def test_contributor_role_allowed(self, tmp_path: Path):
        client = _contributor_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer contrib-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer contrib-test-token"},
            json={"readonly": True},
        )
        assert response.status_code == 200

    def test_viewer_role_forbidden(self, tmp_path: Path):
        client = _viewer_client(tmp_path)
        response = client.patch(
            "/api/v1/credentials/1/policy",
            headers={"Authorization": "Bearer viewer-test-token"},
            json={"readonly": True},
        )
        assert response.status_code == 403


class TestCredentialPolicyUpdateData:
    """Data handling for the policy update endpoint."""

    def test_returns_updated_status(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"readonly": True},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "updated"
        assert body["policy"] is not None
        assert body["policy"]["readonly"] is True

    def test_returns_404_for_nonexistent_credential(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        response = client.patch(
            "/api/v1/credentials/99999/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"readonly": True},
        )
        assert response.status_code == 404

    def test_updates_max_daily_publishes(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"max_daily_publishes": 5},
        )
        assert response.status_code == 200
        assert response.json()["policy"]["max_daily_publishes"] == 5

    def test_updates_allowed_object_kinds(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"allowed_object_kinds": ["skill", "template"]},
        )
        assert response.status_code == 200
        assert response.json()["policy"]["allowed_object_kinds"] == ["skill", "template"]

    def test_updates_multiple_fields(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={
                "max_daily_publishes": 10,
                "allowed_object_kinds": ["skill"],
                "readonly": False,
            },
        )
        assert response.status_code == 200
        policy = response.json()["policy"]
        assert policy["max_daily_publishes"] == 10
        assert policy["allowed_object_kinds"] == ["skill"]
        assert policy["readonly"] is False

    def test_stores_in_resource_selector_when_no_grant(self, tmp_path: Path):
        """When credential has no grant, policy is stored in resource_selector_json._policy."""
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]
        # Bootstrap user has no grant, so policy goes to resource_selector_json

        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"readonly": True},
        )
        assert response.status_code == 200

        # Verify stored in resource_selector_json
        from server.db import get_session_factory
        from server.modules.identity.models import Credential

        factory = get_session_factory()
        with factory() as session:
            cred = session.get(Credential, cred_id)
            rs = json.loads(cred.resource_selector_json)
            assert "_policy" in rs
            assert rs["_policy"]["readonly"] is True

    def test_updates_grant_constraints_when_grant_exists(self, tmp_path: Path):
        """When credential has a grant, policy updates the grant's constraints_json."""
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        principal_id = profile.json()["identity"]["principal_id"]

        from server.db import get_session_factory
        from server.modules.access.models import AccessGrant
        from server.modules.authoring.models import Skill, SkillContent, SkillVersion
        from server.modules.exposure.models import Exposure
        from server.modules.identity.models import Credential, Principal
        from server.modules.identity.service import hash_token
        from server.modules.release.models import Release

        factory = get_session_factory()
        with factory() as session:
            # Create a grant chain
            namespace = Principal(
                kind="user",
                slug="policy-grant-ns",
                display_name="Policy Grant NS",
            )
            session.add(namespace)
            session.flush()

            skill = Skill(
                namespace_id=namespace.id,
                slug="policy-test-skill",
                display_name="Policy Test Skill",
            )
            session.add(skill)
            session.flush()

            content = SkillContent(
                public_id="cnt_policygrantfixture",
                skill_id=skill.id,
                storage_uri="objects/sha256/policy-grant",
                sha256="b" * 64,
                size_bytes=1,
                declared_version="1.0.0",
                state="consumed",
                created_by_principal_id=namespace.id,
            )
            session.add(content)
            session.flush()
            sv = SkillVersion(
                skill_id=skill.id,
                content_id=content.id,
                version="1.0.0",
                content_digest="abc",
                metadata_digest="def",
            )
            session.add(sv)
            session.flush()

            release = Release(
                skill_version_id=sv.id,
                skill_id=skill.id,
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

            constraints = json.dumps({"existing_key": "existing_value"})
            grant = AccessGrant(
                exposure_id=exposure.id,
                grant_type="token",
                subject_ref=f"principal:{principal_id}",
                constraints_json=constraints,
                state="active",
            )
            session.add(grant)
            session.flush()

            raw = "policy_grant_test_token"
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
            grant_cred_id = cred.id
            grant_id = grant.id

        # Update policy via the endpoint
        response = client.patch(
            f"/api/v1/credentials/{grant_cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"max_daily_publishes": 3},
        )
        assert response.status_code == 200
        policy = response.json()["policy"]
        assert policy["max_daily_publishes"] == 3
        assert policy["existing_key"] == "existing_value"

        # Verify grant constraints were updated in DB
        with factory() as session:
            grant = session.get(AccessGrant, grant_id)
            updated = json.loads(grant.constraints_json)
            assert updated["max_daily_publishes"] == 3
            assert updated["existing_key"] == "existing_value"

    def test_empty_body_returns_current_policy(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        # First set a policy
        client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"readonly": True},
        )

        # Empty body should return current policy
        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={},
        )
        assert response.status_code == 200
        assert response.json()["policy"]["readonly"] is True

    def test_incremental_update_merges_with_existing(self, tmp_path: Path):
        client = _profile_client(tmp_path)
        profile = client.get(
            "/api/v1/profile/me",
            headers={"Authorization": "Bearer profile-test-token"},
        )
        cred_id = profile.json()["identity"]["credential_id"]

        # Set initial policy
        client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"max_daily_publishes": 5, "readonly": True},
        )

        # Update only one field
        response = client.patch(
            f"/api/v1/credentials/{cred_id}/policy",
            headers={"Authorization": "Bearer profile-test-token"},
            json={"max_daily_publishes": 10},
        )
        assert response.status_code == 200
        policy = response.json()["policy"]
        assert policy["max_daily_publishes"] == 10
        assert policy["readonly"] is True  # preserved
