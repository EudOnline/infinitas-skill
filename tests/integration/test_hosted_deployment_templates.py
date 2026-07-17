from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_ENV_EXAMPLE = ROOT / ".env.compose.example"
DEPLOYMENT_DOC = ROOT / "docs" / "ops" / "server-deployment.md"


def test_compose_env_example_includes_required_production_fields() -> None:
    env_text = COMPOSE_ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "INFINITAS_SERVER_ENV=production" in env_text
    assert 'INFINITAS_SERVER_ALLOWED_HOSTS=["127.0.0.1","localhost"]' in env_text
    bootstrap_line = next(
        line
        for line in env_text.splitlines()
        if line.startswith("INFINITAS_SERVER_BOOTSTRAP_USERS=")
    )
    users = json.loads(bootstrap_line.partition("=")[2])
    assert all(user.get("password") for user in users)
    assert all(user.get("token") for user in users)
    assert all(user["password"] != user["token"] for user in users)


def test_compose_templates_document_host_uid_gid_override() -> None:
    env_text = COMPOSE_ENV_EXAMPLE.read_text(encoding="utf-8")
    doc_text = DEPLOYMENT_DOC.read_text(encoding="utf-8")

    assert "id -u" in env_text
    assert "id -g" in env_text
    assert "id -u" in doc_text
    assert "id -g" in doc_text


def test_compose_bootstrap_contract_supports_first_browser_login(monkeypatch, tmp_path) -> None:
    env_text = COMPOSE_ENV_EXAMPLE.read_text(encoding="utf-8")
    bootstrap_line = next(
        line
        for line in env_text.splitlines()
        if line.startswith("INFINITAS_SERVER_BOOTSTRAP_USERS=")
    )
    users = json.loads(bootstrap_line.partition("=")[2])
    users[0]["password"] = "ComposeLogin123!"
    users[0]["token"] = "compose-agent-token-value"
    users[1]["password"] = "ContributorLogin123!"
    users[1]["token"] = "contributor-agent-token-value"
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "production")
    monkeypatch.setenv("INFINITAS_SERVER_DATABASE_URL", f"sqlite:///{tmp_path / 'server.db'}")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "Xn9pL2vQ4sT7wZ1aB3cD5eF7gH9jK1mN")
    monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["testserver"]')
    monkeypatch.setenv("INFINITAS_SERVER_BOOTSTRAP_USERS", json.dumps(users))
    monkeypatch.setenv("INFINITAS_SERVER_ARTIFACT_PATH", str(tmp_path / "artifacts"))
    monkeypatch.setenv("INFINITAS_REGISTRY_READ_TOKENS", "[]")

    from server.app import create_app

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "maintainer", "password": "ComposeLogin123!"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def test_production_rejects_token_only_bootstrap_maintainer(monkeypatch) -> None:
    monkeypatch.setenv("INFINITAS_SERVER_ENV", "production")
    monkeypatch.setenv("INFINITAS_SERVER_SECRET_KEY", "Xn9pL2vQ4sT7wZ1aB3cD5eF7gH9jK1mN")
    monkeypatch.setenv("INFINITAS_SERVER_ALLOWED_HOSTS", '["registry.example.com"]')
    monkeypatch.setenv(
        "INFINITAS_SERVER_BOOTSTRAP_USERS",
        '[{"username":"maintainer","role":"maintainer","token":"agent-only-token"}]',
    )
    monkeypatch.setenv("INFINITAS_REGISTRY_READ_TOKENS", "[]")
    from server.settings import get_settings

    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="valid password"):
        get_settings()
