from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _background_client(tmp_path: Path) -> TestClient:
    import os
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'bg.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "bg-test-secret"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"bg-tester","display_name":"BG Tester",'
        '"role":"maintainer","token":"bg-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestBackgroundPresets:
    def test_get_presets_no_auth(self, tmp_path: Path):
        client = _background_client(tmp_path)
        response = client.get("/api/background/presets")
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        assert "light" in data["presets"]
        assert "dark" in data["presets"]
        assert len(data["presets"]["light"]) == 5
        assert len(data["presets"]["dark"]) == 5
        # Verify all external URLs are removed (None)
        for theme in ["light", "dark"]:
            for preset in data["presets"][theme]:
                assert preset["url"] is None

    def test_get_presets_structure(self, tmp_path: Path):
        client = _background_client(tmp_path)
        response = client.get("/api/background/presets")
        data = response.json()
        for preset in data["presets"]["light"]:
            assert "id" in preset
            assert "name" in preset
            assert "url" in preset


class TestUserBackground:
    def test_get_user_background_requires_auth(self, tmp_path: Path):
        client = _background_client(tmp_path)
        response = client.get("/api/background/me")
        assert response.status_code == 401

    def test_get_user_background(self, tmp_path: Path):
        client = _background_client(tmp_path)
        headers = {"Authorization": "Bearer bg-test-token"}
        response = client.get("/api/background/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "light_bg_id" in data
        assert "dark_bg_id" in data

    def test_set_background(self, tmp_path: Path):
        client = _background_client(tmp_path)
        headers = {"Authorization": "Bearer bg-test-token"}
        response = client.post(
            "/api/background/set",
            headers=headers,
            json={"theme": "light", "bg_id": "sakura-street"},
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify it persisted
        me = client.get("/api/background/me", headers=headers)
        assert me.json()["light_bg_id"] == "sakura-street"

    def test_set_background_invalid_theme(self, tmp_path: Path):
        client = _background_client(tmp_path)
        headers = {"Authorization": "Bearer bg-test-token"}
        response = client.post(
            "/api/background/set",
            headers=headers,
            json={"theme": "invalid", "bg_id": "sakura-street"},
        )
        assert response.status_code == 400
        assert "Invalid theme" in response.json()["detail"]

    def test_set_background_invalid_bg_id(self, tmp_path: Path):
        client = _background_client(tmp_path)
        headers = {"Authorization": "Bearer bg-test-token"}
        response = client.post(
            "/api/background/set",
            headers=headers,
            json={"theme": "light", "bg_id": "nonexistent"},
        )
        assert response.status_code == 400
        assert "Invalid background ID" in response.json()["detail"]

    def test_set_background_dark_theme(self, tmp_path: Path):
        client = _background_client(tmp_path)
        headers = {"Authorization": "Bearer bg-test-token"}
        response = client.post(
            "/api/background/set",
            headers=headers,
            json={"theme": "dark", "bg_id": "starry-night"},
        )
        assert response.status_code == 200

        me = client.get("/api/background/me", headers=headers)
        assert me.json()["dark_bg_id"] == "starry-night"
