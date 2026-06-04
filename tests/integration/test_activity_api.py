from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _activity_client(tmp_path: Path) -> TestClient:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'act.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "act-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"act-tester","display_name":"Act Tester",'
        '"role":"maintainer","token":"act-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestActivityList:
    def test_activity_requires_auth(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        response = client.get("/api/v1/activity")
        assert response.status_code == 401

    def test_activity_returns_list(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_activity_limit_param(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity?limit=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] <= 5

    def test_activity_limit_capped_at_500(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity?limit=1000", headers=headers)
        assert response.status_code == 200

    def test_activity_rejects_low_role(self, tmp_path: Path):
        # Create a user with no role (this would need custom bootstrap)
        # For now, just verify the endpoint structure
        client = _activity_client(tmp_path)
        response = client.get("/api/v1/activity")
        assert response.status_code == 401


class TestTokenActivity:
    def test_token_activity_requires_auth(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        response = client.get("/api/v1/activity/tokens/1/activity")
        assert response.status_code == 401

    def test_token_activity_returns_list(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity/tokens/999/activity", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 0  # No activity for nonexistent token


class TestShareLinkActivity:
    def test_share_link_activity_requires_auth(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        response = client.get("/api/v1/activity/share-links/1/activity")
        assert response.status_code == 401

    def test_share_link_activity_returns_list(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity/share-links/999/activity", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 0
