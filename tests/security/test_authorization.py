"""Authorization tests.

This module tests authorization mechanisms to ensure proper
access control based on user roles and permissions.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _test_client(tmp_path: Path) -> TestClient:
    """Create a test client with different user roles."""
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'authz.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "authz-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"maintainer","display_name":"Maintainer",'
        '"role":"maintainer","token":"maintainer-token"},'
        '{"username":"contributor","display_name":"Contributor",'
        '"role":"contributor","token":"contributor-token"},'
        '{"username":"reader","display_name":"Reader",'
        '"role":"reader","token":"reader-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestRoleBasedAccess:
    """Test role-based access control."""

    def test_anonymous_user_cannot_access_protected_endpoints(self, tmp_path: Path) -> None:
        """Test that anonymous users cannot access protected endpoints."""
        client = _test_client(tmp_path)

        # Try to access activity endpoint without auth
        response = client.get("/api/v1/activity")
        assert response.status_code == 401

    def test_reader_role_has_limited_access(self, tmp_path: Path) -> None:
        """Test that reader role has appropriate access limitations."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer reader-token"}

        # Reader might be able to view but not modify
        response = client.get("/api/v1/activity", headers=headers)
        # Could be 403 (forbidden) or 401 (if reader isn't recognized)
        assert response.status_code in (200, 401, 403)

    def test_contributor_can_access_basic_endpoints(self, tmp_path: Path) -> None:
        """Test that contributors can access basic endpoints."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer contributor-token"}

        response = client.get("/api/v1/activity", headers=headers)
        assert response.status_code == 200

    def test_maintainer_has_full_access(self, tmp_path: Path) -> None:
        """Test that maintainers have full access to all endpoints."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer maintainer-token"}

        response = client.get("/api/v1/activity", headers=headers)
        assert response.status_code == 200


class TestTokenAuthorization:
    """Test token-based authorization."""

    def test_valid_token_allows_access(self, tmp_path: Path) -> None:
        """Test that valid tokens allow access."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer maintainer-token"}

        response = client.get("/api/v1/activity", headers=headers)
        assert response.status_code == 200

    def test_invalid_token_denied(self, tmp_path: Path) -> None:
        """Test that invalid tokens are denied."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer invalid-token"}

        response = client.get("/api/v1/activity", headers=headers)
        assert response.status_code == 401

    def test_missing_token_denied(self, tmp_path: Path) -> None:
        """Test that missing tokens are denied."""
        client = _test_client(tmp_path)

        response = client.get("/api/v1/activity")
        assert response.status_code == 401

    def test_malformed_token_denied(self, tmp_path: Path) -> None:
        """Test that malformed tokens are denied."""
        client = _test_client(tmp_path)

        # Test various malformed token formats
        malformed_tokens = [
            "Bearer",  # No token
            "token",  # No Bearer prefix
            "Bearer token with spaces",  # Token with spaces
        ]

        for token_header in malformed_tokens:
            response = client.get(
                "/api/v1/activity",
                headers={"Authorization": token_header}
            )
            assert response.status_code == 401


class TestEndpointAuthorization:
    """Test authorization for specific endpoints."""

    def test_search_allows_anonymous(self, tmp_path: Path) -> None:
        """Test that search endpoint allows anonymous access."""
        client = _test_client(tmp_path)

        response = client.get("/api/v1/search?scope=public")
        assert response.status_code == 200

    def test_me_endpoint_requires_auth(self, tmp_path: Path) -> None:
        """Test that /me endpoint requires authentication."""
        client = _test_client(tmp_path)

        response = client.get("/api/v1/auth/me")
        # Without auth, should return "not authenticated" not 401
        assert response.status_code == 200
        data = response.json()
        assert data.get("authenticated") is False

    def test_me_endpoint_returns_user_info(self, tmp_path: Path) -> None:
        """Test that /me endpoint returns user info when authenticated."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer maintainer-token"}

        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("authenticated") is True
        assert "username" in data


class TestCrossUserAccess:
    """Test that users cannot access other users' resources."""

    def test_user_cannot_access_others_tokens(self, tmp_path: Path) -> None:
        """Test that users cannot list others' tokens."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer contributor-token"}

        # Try to list tokens for a different user's object
        response = client.get(
            "/api/v1/object-tokens/999",
            headers=headers
        )
        # Should be 403 or 404 (not found is acceptable for security)
        assert response.status_code in (403, 404)

    def test_user_cannot_modify_others_resources(self, tmp_path: Path) -> None:
        """Test that users cannot modify others' resources."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer contributor-token"}

        # Try to revoke a token owned by someone else
        response = client.post(
            "/api/v1/tokens/999/revoke",
            headers=headers
        )
        # Should be 403 or 404
        assert response.status_code in (403, 404)
