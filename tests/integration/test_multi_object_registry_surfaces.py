from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

from fastapi.testclient import TestClient

from infinitas_skill.cli.main import main as cli_main
from tests.integration.test_agent_code_import import _create_external_agent_repo
from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)


def _create_skill_release(client: TestClient) -> None:
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    create_skill = client.post(
        "/api/v1/skills",
        headers=headers,
        json={
            "slug": "demo-skill",
            "display_name": "Demo Skill",
            "summary": "Plain skill fixture",
        },
    )
    assert create_skill.status_code == 201, create_skill.text
    skill_id = int(create_skill.json()["id"])
    draft = client.post(
        f"/api/v1/skills/{skill_id}/drafts",
        headers=headers,
        json={
            "content_ref": "git+https://example.com/demo-skill.git#0123456789abcdef0123456789abcdef01234567",
            "metadata": {"entrypoint": "SKILL.md"},
        },
    )
    assert draft.status_code == 201, draft.text
    draft_id = int(draft.json()["id"])
    seal = client.post(
        f"/api/v1/drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "1.0.0"},
    )
    assert seal.status_code == 201, seal.text
    version_id = int(seal.json()["skill_version"]["id"])
    release = client.post(f"/api/v1/versions/{version_id}/releases", headers=headers)
    assert release.status_code == 201, release.text
    release_id = int(release.json()["id"])
    return release_id


def _create_agent_preset_release(client: TestClient) -> int:
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    create_preset = client.post(
        "/api/v1/agent-presets",
        headers=headers,
        json={
            "slug": "shared-soul",
            "display_name": "Shared Soul",
            "summary": "Shared OpenClaw preset",
            "runtime_family": "openclaw",
            "supported_memory_modes": ["local", "shared"],
            "default_memory_mode": "shared",
            "pinned_skill_dependencies": ["fixture-maintainer/demo-skill@1.0.0"],
        },
    )
    assert create_preset.status_code == 201, create_preset.text
    preset_id = int(create_preset.json()["id"])
    draft = client.post(
        f"/api/v1/agent-presets/{preset_id}/drafts",
        headers=headers,
        json={"prompt": "You are shared soul.", "model": "gpt-5.4", "tools": ["shell"]},
    )
    assert draft.status_code == 201, draft.text
    draft_id = int(draft.json()["id"])
    seal = client.post(
        f"/api/v1/agent-preset-drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    assert seal.status_code == 201, seal.text
    version_id = int(seal.json()["skill_version"]["id"])
    release = client.post(f"/api/v1/versions/{version_id}/releases", headers=headers)
    assert release.status_code == 201, release.text
    return int(release.json()["id"])


def _create_agent_code_release(client: TestClient, *, upstream_repo: Path, commit: str) -> int:
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    create_code = client.post(
        "/api/v1/agent-codes",
        headers=headers,
        json={
            "slug": "nano-runner",
            "display_name": "Nano Runner",
            "summary": "Agent code fixture",
            "runtime_family": "openclaw",
            "language": "python",
            "entrypoint": "main.py",
        },
    )
    assert create_code.status_code == 201, create_code.text
    code_id = int(create_code.json()["id"])
    draft = client.post(
        f"/api/v1/agent-codes/{code_id}/drafts",
        headers=headers,
        json={"content_ref": f"git+file://{upstream_repo.resolve()}#{commit}"},
    )
    assert draft.status_code == 201, draft.text
    draft_id = int(draft.json()["id"])
    seal = client.post(
        f"/api/v1/agent-code-drafts/{draft_id}/seal",
        headers=headers,
        json={"version": "0.1.0"},
    )
    assert seal.status_code == 201, seal.text
    version_id = int(seal.json()["skill_version"]["id"])
    release = client.post(f"/api/v1/versions/{version_id}/releases", headers=headers)
    assert release.status_code == 201, release.text
    return int(release.json()["id"])


def _activate_private_exposure(client: TestClient, release_id: int) -> None:
    response = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
        json={
            "audience_type": "private",
            "listing_mode": "listed",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert response.status_code == 201, response.text


def _cli_resolve_registry_plan(entry: dict, *, memory_mode: str | None = None) -> dict:
    args = ["install", "resolve-plan", "--registry-entry-json", json.dumps(entry), "--json"]
    if memory_mode is not None:
        args.extend(["--memory-mode", memory_mode])
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main(args)
    assert code == 0, stderr.getvalue()
    return json.loads(stdout.getvalue())


def test_registry_and_install_surfaces_list_skill_preset_and_agent_code(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    upstream_repo = tmp_path / "external-agent-code"
    commit = _create_external_agent_repo(upstream_repo)

    from server.app import create_app
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_ids = [
        _create_skill_release(client),
        _create_agent_preset_release(client),
        _create_agent_code_release(client, upstream_repo=upstream_repo, commit=commit),
    ]

    processed = run_worker_loop(limit=3)
    assert processed == 3
    for release_id in release_ids:
        _activate_private_exposure(client, release_id)

    ai_index = client.get(
        "/registry/ai-index.json",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert ai_index.status_code == 200, ai_index.text
    ai_payload = ai_index.json()
    by_name = {item["qualified_name"]: item for item in ai_payload["skills"]}
    assert by_name["fixture-maintainer/demo-skill"]["kind"] == "skill"
    assert by_name["fixture-maintainer/shared-soul"]["kind"] == "agent_preset"
    assert by_name["fixture-maintainer/nano-runner"]["kind"] == "agent_code"

    discovery_index = client.get(
        "/registry/discovery-index.json",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert discovery_index.status_code == 200, discovery_index.text
    discovery_payload = discovery_index.json()
    discovered = {item["qualified_name"]: item for item in discovery_payload["skills"]}
    assert discovered["fixture-maintainer/demo-skill"]["kind"] == "skill"
    assert discovered["fixture-maintainer/shared-soul"]["kind"] == "agent_preset"
    assert discovered["fixture-maintainer/nano-runner"]["kind"] == "agent_code"

    preset_plan = _cli_resolve_registry_plan(
        by_name["fixture-maintainer/shared-soul"], memory_mode="shared"
    )
    assert preset_plan["root"]["kind"] == "agent_preset"
    assert preset_plan["root"]["selected_memory_mode"] == "shared"

    code_plan = _cli_resolve_registry_plan(by_name["fixture-maintainer/nano-runner"])
    assert code_plan["root"]["kind"] == "agent_code"

    skill_plan = _cli_resolve_registry_plan(by_name["fixture-maintainer/demo-skill"])
    assert skill_plan["root"]["kind"] == "skill"
