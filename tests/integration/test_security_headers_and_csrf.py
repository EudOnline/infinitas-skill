from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _security_client(tmp_path: Path) -> TestClient:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'security.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "security-test-secret"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"security-tester","display_name":"Security Tester",'
        '"role":"maintainer","token":"security-test-token","password":"security-test-password"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestSecurityHeaders:
    def test_csp_header_present(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/")
        assert response.status_code in (200, 307, 404)
        assert "content-security-policy" in response.headers
        csp = response.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "style-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_x_frame_options_deny(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/")
        assert "x-frame-options" in response.headers
        assert response.headers["x-frame-options"] == "DENY"

    def test_x_content_type_options_nosniff(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/")
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_referrer_policy_strict(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/")
        assert "referrer-policy" in response.headers
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_hsts_present(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/")
        assert "strict-transport-security" in response.headers
        hsts = response.headers["strict-transport-security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts


class TestCsrfProtection:
    def test_get_requests_skip_csrf(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/api/v1/me", headers={"Authorization": "Bearer security-test-token"})
        assert response.status_code == 200

    def test_bearer_auth_skips_csrf(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer security-test-token"},
        )
        assert response.status_code == 200

    def test_unauthenticated_post_skips_csrf(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.post("/api/auth/logout")
        assert response.status_code == 200

    def test_csrf_missing_rejected_for_cookie_auth(self, tmp_path: Path):
        client = _security_client(tmp_path)
        login = client.post(
            "/api/auth/login",
            json={"username": "security-tester", "password": "security-test-password"},
        )
        assert login.status_code == 200
        assert "csrf_token" in login.cookies

        response = client.post("/api/auth/logout")
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF token missing"

    def test_csrf_mismatch_rejected(self, tmp_path: Path):
        client = _security_client(tmp_path)
        login = client.post(
            "/api/auth/login",
            json={"username": "security-tester", "password": "security-test-password"},
        )
        assert login.status_code == 200

        response = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": "wrong-token"},
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "CSRF token mismatch"

    def test_csrf_valid_allows_cookie_auth_post(self, tmp_path: Path):
        client = _security_client(tmp_path)
        login = client.post(
            "/api/auth/login",
            json={"username": "security-tester", "password": "security-test-password"},
        )
        assert login.status_code == 200
        csrf_cookie = login.cookies["csrf_token"]

        response = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_cookie},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True


class TestCookieSecurity:
    def test_auth_cookie_httponly(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.post(
            "/api/auth/login",
            json={"username": "security-tester", "password": "security-test-password"},
        )
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "HttpOnly" in set_cookie
        assert "SameSite=lax" in set_cookie or "samesite=lax" in set_cookie.lower()

    def test_csrf_cookie_not_httponly(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.post(
            "/api/auth/login",
            json={"username": "security-tester", "password": "security-test-password"},
        )
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        csrf_cookie_part = [c for c in set_cookie.split(", ") if "csrf_token" in c]
        if csrf_cookie_part:
            assert "HttpOnly" not in csrf_cookie_part[0]

    def test_csrf_endpoint_refreshes_token(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/api/auth/csrf")
        assert response.status_code == 200
        assert "csrf_token" in response.json()
        assert "csrf_token" in response.cookies


class TestExceptionHandlers:
    def test_404_returns_json_for_api(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/api/nonexistent", headers={"Accept": "application/json"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

    def test_404_renders_html_for_browser(self, tmp_path: Path):
        client = _security_client(tmp_path)
        response = client.get("/nonexistent-page", headers={"Accept": "text/html"})
        assert response.status_code == 404
        assert "text/html" in response.headers.get("content-type", "")
        assert "Not Found" in response.text or "404" in response.text

    def test_500_handler_registered(self, tmp_path: Path):
        from server.app import app
        assert any(str(500) in str(k) for k in app.exception_handlers)
