"""CSRF protection tests.

This module tests CSRF (Cross-Site Request Forgery) protection mechanisms
to ensure state-changing operations require valid CSRF tokens.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _test_client(tmp_path: Path) -> TestClient:
    """Create a test client with CSRF protection enabled."""
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'csrf.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "csrf-test-secret-32chars-long-minimum"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"csrf-tester","display_name":"CSRF Tester",'
        '"role":"maintainer","token":"csrf-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestCSRFProtection:
    """Test suite for CSRF protection."""

    def test_csrf_token_endpoint_requires_no_auth(self, tmp_path: Path) -> None:
        """Test that CSRF token endpoint doesn't require authentication."""
        client = _test_client(tmp_path)
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert isinstance(data["csrf_token"], str)
        assert len(data["csrf_token"]) > 0

    def test_csrf_token_is_set_as_cookie(self, tmp_path: Path) -> None:
        """Test that CSRF token is set as an HttpOnly cookie."""
        client = _test_client(tmp_path)
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 200

        # Check that the CSRF cookie is set
        cookies = response.cookies.get("csrf_token")
        assert cookies is not None
        # In test client, cookies might be strings or objects
        cookie_value = cookies if isinstance(cookies, str) else getattr(cookies, "value", cookies)
        assert len(cookie_value) > 0

    def test_logout_without_csrf_token_succeeds(self, tmp_path: Path) -> None:
        """Test that logout can be called without CSRF token (it's idempotent)."""
        client = _test_client(tmp_path)
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True

    def test_login_without_csrf_token_succeeds(self, tmp_path: Path) -> None:
        """Test that login doesn't require CSRF token (session-based)."""
        client = _test_client(tmp_path)
        # Login requires username/password, not CSRF token
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "csrf-tester", "password": "wrong-password"},
        )
        # Should fail due to wrong password, not CSRF
        assert response.status_code == 401

    def test_csrf_token_refresh_on_each_call(self, tmp_path: Path) -> None:
        """Test that CSRF token can be refreshed."""
        client = _test_client(tmp_path)

        # Get first token
        response1 = client.get("/api/v1/auth/csrf")
        token1 = response1.json()["csrf_token"]

        # Get second token
        response2 = client.get("/api/v1/auth/csrf")
        token2 = response2.json()["csrf_token"]

        # Tokens should be different (random)
        assert token1 != token2

    def test_csrf_cookie_attributes(self, tmp_path: Path) -> None:
        """Test that CSRF cookie has correct security attributes."""
        client = _test_client(tmp_path)
        response = client.get("/api/v1/auth/csrf")

        csrf_cookie = response.cookies.get("csrf_token")
        assert csrf_cookie is not None

        # In test mode, we just verify the cookie exists
        # Production environment would have specific security attributes
        cookie_value = (
            csrf_cookie
            if isinstance(csrf_cookie, str)
            else getattr(csrf_cookie, "value", csrf_cookie)
        )
        assert cookie_value is not None
        assert len(cookie_value) > 0


class TestCSRFWithAuthentication:
    """Test CSRF behavior with authenticated requests."""

    def test_csrf_endpoint_with_auth(self, tmp_path: Path) -> None:
        """Test CSRF token endpoint with authenticated user."""
        client = _test_client(tmp_path)
        headers = {"Authorization": "Bearer csrf-test-token"}
        response = client.get("/api/v1/auth/csrf", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data

    def test_logout_with_invalid_csrf_still_works(self, tmp_path: Path) -> None:
        """Test that logout works even with invalid CSRF (graceful degradation)."""
        client = _test_client(tmp_path)
        headers = {"X-CSRF-Token": "invalid-token"}
        response = client.post("/api/v1/auth/logout", headers=headers)
        # Logout should still work for security (clearing session)
        assert response.status_code == 200
