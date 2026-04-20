from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)


def _run(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def _create_external_agent_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    (path / "main.py").write_text("print('agent code fixture')\n", encoding="utf-8")
    (path / "README.md").write_text("# Agent Code Fixture\n", encoding="utf-8")
    _run(["git", "init", "-b", "main"], cwd=path)
    _run(["git", "config", "user.name", "Agent Code Test"], cwd=path)
    _run(["git", "config", "user.email", "agent-code@example.com"], cwd=path)
    _run(["git", "add", "main.py", "README.md"], cwd=path)
    _run(["git", "commit", "-m", "fixture: initial agent code"], cwd=path)
    return _run(["git", "rev-parse", "HEAD"], cwd=path)


def test_agent_code_external_import_materializes_hosted_bundle(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    artifact_root = _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    upstream_repo = tmp_path / "external-agent-code"
    commit = _create_external_agent_repo(upstream_repo)

    from server.app import create_app
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    headers = {"Authorization": "Bearer fixture-maintainer-token"}

    create_code = client.post(
        "/api/v1/agent-codes",
        headers=headers,
        json={
            "slug": "nano-runner",
            "display_name": "Nano Runner",
            "summary": "Lightweight runnable agent code",
            "runtime_family": "openclaw",
            "language": "python",
            "entrypoint": "main.py",
        },
    )
    assert create_code.status_code == 201, create_code.text
    code_id = int(create_code.json()["id"])

    create_draft = client.post(
        f"/api/v1/agent-codes/{code_id}/drafts",
        headers=headers,
        json={
            "content_ref": f"git+file://{upstream_repo.resolve()}#{commit}",
        },
    )
    assert create_draft.status_code == 201, create_draft.text
    draft_id = int(create_draft.json()["id"])

    seal = client.post(
        f"/api/v1/agent-code-drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    assert seal.status_code == 201, seal.text
    version_id = int(seal.json()["skill_version"]["id"])

    release = client.post(f"/api/v1/versions/{version_id}/releases", headers=headers)
    assert release.status_code == 201, release.text

    processed = run_worker_loop(limit=1)
    assert processed == 1

    bundle_path = (
        artifact_root
        / "skills"
        / "fixture-maintainer"
        / "nano-runner"
        / "0.1.0"
        / "skill.tar.gz"
    )
    assert bundle_path.exists(), "expected materialized hosted bundle"

    with tarfile.open(bundle_path, mode="r:gz") as archive:
        names = set(archive.getnames())

    assert "nano-runner/main.py" in names
    assert "nano-runner/README.md" in names
