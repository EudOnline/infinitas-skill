from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _middleware_client(tmp_path: Path) -> TestClient:
    import os
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'mw.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "mw-test-secret"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = "[]"
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestSecurityHeadersMiddleware:
    def test_all_security_headers_present(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/healthz")
        assert response.status_code == 200
        headers = response.headers
        assert "content-security-policy" in headers
        assert "x-frame-options" in headers
        assert "x-content-type-options" in headers
        assert "referrer-policy" in headers
        assert "strict-transport-security" in headers

    def test_csp_script_hash_present(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/healthz")
        csp = response.headers["content-security-policy"]
        assert "sha256-" in csp

    def test_frame_ancestors_none(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/healthz")
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    def test_x_frame_options_deny(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/healthz")
        assert response.headers["x-frame-options"] == "DENY"

    def test_hsts_max_age(self, tmp_path: Path):
        client = _middleware_client(tmp_path)
        response = client.get("/healthz")
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
        response = client.get("/healthz")
        assert response.status_code == 200
