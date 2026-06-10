from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _auth_client(tmp_path: Path) -> TestClient:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'auth_edge.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "auth-edge-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"edge-tester","display_name":"Edge Tester",'
        '"role":"maintainer","token":"edge-test-token","password":"edge-test-password"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    # Reset global rate limiter so tests don't interfere with each other
    from server.rate_limit import get_rate_limiter
    get_rate_limiter().reset_all()
    return TestClient(create_app())


class TestLoginEdgeCases:
    def test_login_with_empty_credentials(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        response = client.post("/api/v1/auth/login", json={"username": "", "password": ""})
        assert response.status_code == 422

    def test_login_with_wrong_password(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "edge-tester", "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_login_rate_limit(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        # Make multiple failed login attempts quickly
        for _ in range(12):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "edge-tester", "password": "wrong"},
            )
        # After rate limit, should get 429
        assert response.status_code == 429
        # Clean up rate limiter to avoid affecting other tests
        from server.rate_limit import get_rate_limiter
        get_rate_limiter().reset_all()

    def test_login_sets_csrf_cookie(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "edge-tester", "password": "edge-test-password"},
        )
        assert response.status_code == 200
        assert "csrf_token" in response.cookies
        set_cookie = response.headers.get("set-cookie", "")
        assert "csrf_token" in set_cookie

    def test_login_sets_auth_cookie(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "edge-tester", "password": "edge-test-password"},
        )
        assert response.status_code == 200
        assert "infinitas_auth_token" in response.cookies


class TestLogoutEdgeCases:
    def test_logout_without_cookie(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 200

    def test_logout_clears_cookies(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        # Login first
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "edge-tester", "password": "edge-test-password"},
        )
        assert login.status_code == 200
        csrf = login.cookies.get("csrf_token")

        # Logout with CSRF token (cookie auth requires double-submit)
        response = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "infinitas_auth_token" in set_cookie or "Max-Age=0" in set_cookie


class TestCsrfEndpoint:
    def test_csrf_returns_token(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert len(data["csrf_token"]) > 0
        # Cookie should match response body
        assert response.cookies.get("csrf_token") == data["csrf_token"]

    def test_csrf_refreshes_on_each_call(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        r1 = client.get("/api/v1/auth/csrf")
        r2 = client.get("/api/v1/auth/csrf")
        assert r1.json()["csrf_token"] != r2.json()["csrf_token"]


class TestMeEndpoint:
    def test_me_unauthenticated(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["authenticated"] is False

    def test_me_authenticated(self, tmp_path: Path):
        client = _auth_client(tmp_path)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "edge-tester", "password": "edge-test-password"},
        )
        assert login.status_code == 200
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        assert response.json()["authenticated"] is True
        assert response.json()["username"] == "edge-tester"
