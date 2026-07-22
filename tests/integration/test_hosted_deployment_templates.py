from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_ENV_EXAMPLE = ROOT / ".env.compose.example"
COMPOSE_TEMPLATE = ROOT / "docker-compose.yml"
DEPLOYMENT_DOC = ROOT / "docs" / "ops" / "server-deployment.md"
COOLIFY_COMPOSE = ROOT / "docker-compose.coolify.yml"
COOLIFY_DOC = ROOT / "docs" / "ops" / "coolify-deployment.md"
HOSTED_ENTRYPOINT = ROOT / "docker" / "entrypoint-hosted.sh"


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


def test_coolify_compose_freezes_single_node_proxy_and_volume_contract() -> None:
    compose_text = COOLIFY_COMPOSE.read_text(encoding="utf-8")

    assert "init-permissions:" in compose_text
    assert 'user: "0:0"' in compose_text
    assert "chown -R 1000:1000" in compose_text
    assert "app:" in compose_text
    assert "worker:" in compose_text
    worker_text = compose_text.split("\n  worker:\n", 1)[1]
    assert "      - -c\n" in worker_text
    assert "      - -lc\n" not in worker_text
    assert 'expose:\n      - "8000"' in compose_text
    assert "ports:" not in compose_text
    assert "env_file:" not in compose_text
    assert "networks:" not in compose_text
    assert "condition: service_healthy" in compose_text
    assert "/api/v1/system/readyz" in compose_text
    assert "json.loads(os.environ['INFINITAS_SERVER_ALLOWED_HOSTS'])[0]" in compose_text
    assert "'Host':host" in compose_text
    assert "X-Forwarded-Proto':'https" in compose_text
    assert "worker-healthcheck" in compose_text
    assert (
        "PYTHONPATH: /srv/infinitas/repo/src:/opt/infinitas/bundle/src:"
        "/opt/infinitas/bundle" in compose_text
    )
    for volume in (
        "infinitas-repo",
        "infinitas-data",
        "infinitas-artifacts",
        "infinitas-backups",
        "infinitas-home",
    ):
        assert volume in compose_text


def test_hosted_bootstrap_keeps_bundled_server_importable_from_runtime_repo() -> None:
    entrypoint_text = HOSTED_ENTRYPOINT.read_text(encoding="utf-8")
    compose_text = COMPOSE_TEMPLATE.read_text(encoding="utf-8")

    assert 'export PYTHONPATH="$INFINITAS_SERVER_REPO_PATH/src:' in entrypoint_text
    assert "$INFINITAS_BUNDLED_REPO_PATH/src:$INFINITAS_BUNDLED_REPO_PATH" in entrypoint_text
    assert (
        "PYTHONPATH: /srv/infinitas/repo/src:/opt/infinitas/bundle/src:"
        "/opt/infinitas/bundle" in compose_text
    )
    assert "json.loads(os.environ['INFINITAS_SERVER_ALLOWED_HOSTS'])[0]" in compose_text
    assert "'Host':host" in compose_text
    assert "X-Forwarded-Proto':'https" in compose_text


def test_coolify_install_runbook_covers_release_operations() -> None:
    doc_text = COOLIFY_DOC.read_text(encoding="utf-8")
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")

    for marker in (
        "docker-compose.coolify.yml",
        "app` replicas: exactly `1`",
        "worker` replicas: exactly `1`",
        "INFINITAS_SERVER_ALLOWED_HOSTS",
        "/api/v1/system/readyz",
        "worker-healthcheck",
        "Back up before every upgrade",
        "Upgrade and rollback",
        "preserve all five named volumes",
        '"base_url": "https://skills.example.com/api/v1/registry"',
    ):
        assert marker in doc_text
    assert "--target-dir" not in readme_text


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
