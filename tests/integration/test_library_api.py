"""Integration tests for library and object-tokens API endpoints.

Covers:
- Library API validation
- Object token API validation
- Request schema constraints
- Error handling for invalid inputs
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


def _api_client(tmp_path: Path, *, bootstrap_users: str = "[]") -> TestClient:
    """Create a test client with fresh environment."""
    db_path = tmp_path / "lib_test.db"
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "lib-test-secret-key-32chars-long!!!"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = bootstrap_users
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    os.environ["INFINITAS_SERVER_ENVIRONMENT"] = "development"
    from server.rate_limit import get_rate_limiter
    get_rate_limiter().reset_all()
    return TestClient(create_app())


_BOOTSTRAP_USER = (
    '[{"username":"testadmin","display_name":"Test Admin",'
    '"role":"maintainer","token":"admin-token-123","password":"AdminPass123!"}]'
)


def _login_and_get_csrf(client: TestClient) -> str:
    """Login and return CSRF token."""
    resp = client.post("/api/v1/auth/login", json={
        "username": "testadmin",
        "password": "AdminPass123!",
    })
    assert resp.status_code == 200
    return resp.cookies.get("csrf_token", "")


def _auth_headers(csrf: str) -> dict:
    """Return headers with CSRF token."""
    return {"X-CSRF-Token": csrf}


# ---------------------------------------------------------------------------
# Library API validation
# ---------------------------------------------------------------------------
class TestLibraryAPIValidation:
    def test_library_list_requires_auth(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        response = client.get("/api/v1/library/")
        assert response.status_code in (401, 403)

    def test_library_list_with_auth(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.get("/api/v1/library/", headers=_auth_headers(csrf))
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body

    def test_library_object_not_found(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.get("/api/v1/library/99999", headers=_auth_headers(csrf))
        assert response.status_code == 404

    def test_library_token_create_validation(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        # Invalid token_type
        response = client.post(
            "/api/v1/library/releases/1/tokens",
            json={"token_type": "invalid"},
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_library_share_create_validation(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        # Invalid expires_in_days (too high)
        response = client.post(
            "/api/v1/library/releases/1/share-links",
            json={"expires_in_days": 9999},
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_library_share_create_valid(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        # Valid request (release doesn't exist, but validation passes)
        response = client.post(
            "/api/v1/library/releases/1/share-links",
            json={
                "label": "test-share",
                "expires_in_days": 7,
                "usage_limit": 5,
            },
            headers=_auth_headers(csrf),
        )
        # Should fail with 404 (release not found) not 422 (validation error)
        assert response.status_code in (404, 403)


# ---------------------------------------------------------------------------
# Object token API validation
# ---------------------------------------------------------------------------
class TestObjectTokenAPIValidation:
    def test_object_tokens_requires_auth(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        response = client.get("/api/v1/object-tokens/objects/1/tokens")
        assert response.status_code in (401, 403)

    def test_object_token_create_validation_empty_name(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.post(
            "/api/v1/object-tokens/objects/1/tokens",
            json={
                "name": "",
                "type": "reader",
                "scope_type": "release",
                "scope_id": 1,
            },
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_object_token_create_validation_invalid_type(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.post(
            "/api/v1/object-tokens/objects/1/tokens",
            json={
                "name": "test-token",
                "type": "invalid",
                "scope_type": "release",
                "scope_id": 1,
            },
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_object_token_create_validation_zero_scope_id(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.post(
            "/api/v1/object-tokens/objects/1/tokens",
            json={
                "name": "test-token",
                "type": "reader",
                "scope_type": "release",
                "scope_id": 0,
            },
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_object_token_create_validation_expires_too_long(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.post(
            "/api/v1/object-tokens/objects/1/tokens",
            json={
                "name": "test-token",
                "type": "reader",
                "scope_type": "release",
                "scope_id": 1,
                "expires_in_days": 9999,
            },
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Publish API validation
# ---------------------------------------------------------------------------
class TestPublishAPIValidation:
    def test_publish_requires_auth(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        response = client.put(
            "/api/v1/publish/objects/test-skill",
            json={"display_name": "Test Skill"},
        )
        assert response.status_code in (401, 403)

    def test_publish_object_validation_empty_name(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.put(
            "/api/v1/publish/objects/test-skill",
            json={"display_name": ""},
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_publish_object_validation_long_summary(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.put(
            "/api/v1/publish/objects/test-skill",
            json={
                "display_name": "Test Skill",
                "summary": "x" * 3000,  # Exceeds max_length=2000
            },
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_publish_release_validation_invalid_version(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.post(
            "/api/v1/publish/objects/1/releases",
            json={
                "version": "invalid version!",  # Contains space and !
            },
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_publish_release_validation_valid_version(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        # Valid version format (object doesn't exist, but validation passes)
        response = client.post(
            "/api/v1/publish/objects/1/releases",
            json={
                "version": "1.0.0",
                "content_ref": "https://example.com/skill.tar.gz",
            },
            headers=_auth_headers(csrf),
        )
        # Should fail with 404/403 not 422
        assert response.status_code in (404, 403, 401)


# ---------------------------------------------------------------------------
# Profile API validation
# ---------------------------------------------------------------------------
class TestProfileAPIValidation:
    def test_profile_requires_auth(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        response = client.get("/api/v1/profile/me")
        assert response.status_code in (401, 403)

    def test_profile_writeback_validation_long_note(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.post(
            "/api/v1/profile/writeback",
            json={"note": "x" * 5000},  # Exceeds max_length=4096
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_policy_update_validation_negative_publishes(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.patch(
            "/api/v1/credentials/1/policy",
            json={"max_daily_publishes": -1},
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422

    def test_policy_update_validation_excessive_publishes(self, tmp_path: Path):
        client = _api_client(tmp_path, bootstrap_users=_BOOTSTRAP_USER)
        csrf = _login_and_get_csrf(client)
        response = client.patch(
            "/api/v1/credentials/1/policy",
            json={"max_daily_publishes": 999999},
            headers=_auth_headers(csrf),
        )
        assert response.status_code == 422
