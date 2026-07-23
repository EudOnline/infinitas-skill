from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path

import httpx

from tests.integration.test_private_registry_release_materialization import (
    _prepare_signing_repo,
)

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / ".venv" / "bin" / "infinitas"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run(args: list[str], *, env: dict[str, str], expect: int = 0) -> dict:
    result = subprocess.run(
        [str(CLI), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == expect, result.stderr or result.stdout
    if not result.stdout.strip():
        return {}
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def _wait_ready(base_url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        assert process.poll() is None, "acceptance API exited before readiness"
        try:
            if httpx.get(f"{base_url}/api/v1/system/readyz", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise AssertionError("acceptance API did not become ready")


def _create_namespace_tokens(base_url: str) -> tuple[dict, dict]:
    with httpx.Client(base_url=base_url) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "agent-admin", "password": "agent-admin-password"},
        )
        assert login.status_code == 200, login.text
        csrf = client.get("/api/v1/auth/csrf")
        assert csrf.status_code == 200, csrf.text
        headers = {"X-CSRF-Token": csrf.json()["csrf_token"]}
        publisher = client.post(
            "/api/v1/namespace-tokens",
            headers=headers,
            json={
                "name": "acceptance-publisher",
                "type": "publisher",
                "max_daily_publishes": 20,
            },
        )
        reader = client.post(
            "/api/v1/namespace-tokens",
            headers=headers,
            json={"name": "acceptance-reader", "type": "reader"},
        )
        assert publisher.status_code == 201, publisher.text
        assert reader.status_code == 201, reader.text
        return publisher.json(), reader.json()


def _write_skill(source: Path, marker: str) -> None:
    source.mkdir(parents=True, exist_ok=True)
    (source / "SKILL.md").write_text(
        "---\n"
        "name: agent-lifecycle-acceptance\n"
        "description: Verify the complete Agent-hosted lifecycle.\n"
        "---\n\n"
        "# Agent Lifecycle Acceptance\n\n"
        f"Release marker: {marker}.\n",
        encoding="utf-8",
    )


def test_cross_process_agent_lifecycle(
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    (tmp_path / "artifacts").mkdir()
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
            "INFINITAS_SERVER_ENV": "test",
            "INFINITAS_SERVER_DATABASE_URL": f"sqlite:///{tmp_path / 'acceptance.db'}",
            "INFINITAS_SERVER_SECRET_KEY": "agent-lifecycle-acceptance-secret-key",
            "INFINITAS_SERVER_ALLOWED_HOSTS": json.dumps(["127.0.0.1", "localhost"]),
            "INFINITAS_SERVER_ARTIFACT_PATH": str(tmp_path / "artifacts"),
            "INFINITAS_SERVER_REPO_PATH": str(temp_repo_copy),
            "INFINITAS_SKILL_GIT_SIGNING_KEY": str(signing_key),
            "INFINITAS_SERVER_BOOTSTRAP_USERS": json.dumps(
                [
                    {
                        "username": "agent-admin",
                        "display_name": "Agent Admin",
                        "role": "maintainer",
                        "token": "agent-admin-personal-token",
                        "password": "agent-admin-password",
                    }
                ]
            ),
        }
    )
    api = subprocess.Popen(
        [
            str(ROOT / ".venv" / "bin" / "uvicorn"),
            "server.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    worker: subprocess.Popen | None = None
    try:
        _wait_ready(base_url, api)
        worker = subprocess.Popen(
            [str(CLI), "server", "worker", "--poll-interval", "0.1"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        publisher, reader = _create_namespace_tokens(base_url)
        source = tmp_path / "source"
        _write_skill(source, "1.0.0")
        publish_env = dict(
            env,
            INFINITAS_REGISTRY_API_BASE_URL=base_url,
            INFINITAS_REGISTRY_API_TOKEN=publisher["raw_token"],
        )
        first = _run(
            [
                "registry",
                "publish",
                str(source),
                "--version",
                "1.0.0",
                "--repo-root",
                str(temp_repo_copy),
            ],
            env=publish_env,
        )
        assert first["state"] == "published"
        assert first["reused_version"] is False

        _write_skill(source, "1.1.0")
        second = _run(
            [
                "registry",
                "publish",
                str(source),
                "--version",
                "1.1.0",
                "--repo-root",
                str(temp_repo_copy),
            ],
            env=publish_env,
        )
        repeated = _run(
            [
                "registry",
                "publish",
                str(source),
                "--version",
                "1.1.0",
                "--repo-root",
                str(temp_repo_copy),
            ],
            env=publish_env,
        )
        assert second["version"]["content_digest"] != first["version"]["content_digest"]
        assert repeated["reused_version"] is True

        _write_skill(source, "conflicting-1.1.0")
        conflict = subprocess.run(
            [
                str(CLI),
                "registry",
                "publish",
                str(source),
                "--version",
                "1.1.0",
                "--repo-root",
                str(temp_repo_copy),
                "--receipt",
                str(tmp_path / "conflict-receipt.json"),
            ],
            cwd=ROOT,
            env=publish_env,
            text=True,
            capture_output=True,
        )
        assert conflict.returncode == 1
        assert "different content digest" in conflict.stderr

        release_id = int(second["release"]["id"])
        _run(
            [
                "registry",
                "exposures",
                "create",
                str(release_id),
                "--audience-type",
                "grant",
                "--listing-mode",
                "direct_only",
            ],
            env=publish_env,
        )
        share = _run(
            ["registry", "shares", "create", str(release_id), "--name", "acceptance"],
            env=publish_env,
        )
        share_env = dict(env, INFINITAS_SHARE_SECRET=share["resolve_secret"])
        shared_target = tmp_path / "shared-install"
        installed_share = _run(
            [
                "install",
                "from-share",
                share["resolve_url"],
                str(shared_target),
                "--repo-root",
                str(temp_repo_copy),
                "--json",
            ],
            env=share_env,
        )
        assert installed_share["resolved_version"] == "1.1.0"
        _run(["registry", "shares", "revoke", str(share["id"])], env=publish_env)

        workspace = tmp_path / "workspace"
        read_env = dict(env, ACCEPTANCE_READER_TOKEN=reader["raw_token"])
        bootstrapped = _run(
            [
                "registry",
                "bootstrap",
                "hosted",
                f"{base_url}/api/v1/registry",
                "--repo-root",
                str(workspace),
                "--token-env",
                "ACCEPTANCE_READER_TOKEN",
                "--set-default",
                "--json",
            ],
            env=read_env,
        )
        assert bootstrapped["trust_changed"] is True
        _run(
            [
                "registry",
                "sources",
                "--repo-root",
                str(workspace),
                "sync",
                "hosted",
                "--json",
            ],
            env=read_env,
        )
        managed_target = tmp_path / "managed-install"
        exact = _run(
            [
                "install",
                "exact",
                "agent-admin/agent-lifecycle-acceptance",
                str(managed_target),
                "--version",
                "1.0.0",
                "--registry",
                "hosted",
                "--repo-root",
                str(workspace),
                "--json",
            ],
            env=read_env,
        )
        assert exact["resolved_version"] == "1.0.0"
        switched = _run(
            [
                "install",
                "switch",
                "agent-lifecycle-acceptance",
                str(managed_target),
                "--to-version",
                "1.1.0",
                "--registry",
                "hosted",
                "--repo-root",
                str(workspace),
                "--json",
            ],
            env=read_env,
        )
        assert switched["state"] == "switched"
        rolled_back = _run(
            [
                "install",
                "rollback",
                "agent-lifecycle-acceptance",
                str(managed_target),
                "--repo-root",
                str(workspace),
                "--json",
            ],
            env=read_env,
        )
        assert rolled_back["from_version"] == "1.1.0"
        assert rolled_back["to_version"] == "1.0.0"
    finally:
        if worker is not None:
            worker.terminate()
            worker.wait(timeout=10)
        api.terminate()
        api.wait(timeout=10)
