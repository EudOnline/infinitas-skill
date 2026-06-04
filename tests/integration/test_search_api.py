from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _search_client(tmp_path: Path) -> TestClient:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'search.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "search-test-secret-32chars-long-minimum"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"search-tester","display_name":"Search Tester",'
        '"role":"maintainer","token":"search-test-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestSearchApi:
    def test_search_public_no_auth(self, tmp_path: Path):
        client = _search_client(tmp_path)
        response = client.get("/api/v1/search?scope=public")
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data
        assert "commands" in data
        assert isinstance(data["skills"], list)

    def test_search_me_requires_auth(self, tmp_path: Path):
        client = _search_client(tmp_path)
        response = client.get("/api/v1/search?scope=me")
        assert response.status_code == 401

    def test_search_me_with_auth(self, tmp_path: Path):
        client = _search_client(tmp_path)
        headers = {"Authorization": "Bearer search-test-token"}
        response = client.get("/api/v1/search?scope=me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data

    def test_search_with_query(self, tmp_path: Path):
        client = _search_client(tmp_path)
        response = client.get("/api/v1/search?q=test&scope=public")
        assert response.status_code == 200

    def test_search_invalid_scope_rejected(self, tmp_path: Path):
        client = _search_client(tmp_path)
        response = client.get("/api/v1/search?scope=invalid")
        assert response.status_code == 422

    def test_search_with_limit(self, tmp_path: Path):
        client = _search_client(tmp_path)
        response = client.get("/api/v1/search?limit=5&scope=public")
        assert response.status_code == 200

    def test_search_limit_out_of_range(self, tmp_path: Path):
        client = _search_client(tmp_path)
        response = client.get("/api/v1/search?limit=100&scope=public")
        # Should be rejected by Pydantic validator (max 20)
        assert response.status_code == 422
