from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _middleware_client(tmp_path: Path) -> TestClient:
    import os

    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'mw.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "mw-test-secret-32chars-long-minimum"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"middleware-tester","display_name":"Middleware Tester",'
        '"role":"maintainer","token":"middleware-token","password":"MiddlewarePass123!"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestSecurityHeadersMiddleware:
    def test_all_security_headers_present(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/api/v1/system/healthz")
        assert response.status_code == 200
        headers = response.headers
        assert "content-security-policy" in headers
        assert "x-frame-options" in headers
        assert "x-content-type-options" in headers
        assert "referrer-policy" in headers
        assert "strict-transport-security" in headers

    def test_csp_script_hash_present(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/api/v1/system/healthz")
        csp = response.headers["content-security-policy"]
        assert "sha256-" in csp

    def test_frame_ancestors_none(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/api/v1/system/healthz")
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    def test_x_frame_options_deny(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/api/v1/system/healthz")
        assert response.headers["x-frame-options"] == "DENY"

    def test_hsts_max_age(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/api/v1/system/healthz")
        hsts = response.headers["strict-transport-security"]
        assert "max-age=31536000" in hsts

    def test_headers_on_static_route(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        # Static routes also get security headers
        response = client.get("/static/css/output.css")
        # 200 if file exists, 404 otherwise — headers should still be present
        assert "content-security-policy" in response.headers


class TestCsrfValidationMiddleware:
    def test_websocket_skips_csrf(self, tmp_path: Path):
        # ASGI middleware should skip non-http scopes
        # We can't easily test websockets here, but we verify the middleware
        # doesn't crash on a normal request
        client = _middleware_client(tmp_path)
        response = client.get("/api/v1/system/healthz")
        assert response.status_code == 200


class TestRequestContextMiddleware:
    def test_generates_unique_request_id_for_each_response(self, tmp_path: Path):
        client = _middleware_client(tmp_path)

        first = client.get("/api/v1/system/healthz", headers={"X-Request-ID": "client-chosen"})
        second = client.get("/api/v1/system/healthz")

        assert len(first.headers["x-request-id"]) == 32
        assert first.headers["x-request-id"].isalnum()
        assert first.headers["x-request-id"] != "client-chosen"
        assert second.headers["x-request-id"] != first.headers["x-request-id"]

    def test_adds_request_id_to_not_found_and_csrf_rejection(self, tmp_path: Path):
        client = _middleware_client(tmp_path)

        missing = client.get("/api/v1/missing")
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "middleware-tester", "password": "MiddlewarePass123!"},
        )
        csrf_rejected = client.post("/api/v1/auth/logout")

        assert missing.status_code == 404
        assert login.status_code == 200
        assert csrf_rejected.status_code == 403
        assert "x-request-id" in missing.headers
        assert "x-request-id" in csrf_rejected.headers
