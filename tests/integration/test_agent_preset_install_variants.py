from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from infinitas_skill.install.service import plan_from_registry_entry
from tests.integration.test_private_registry_release_materialization import (
    _configure_env,
    _prepare_signing_repo,
)


def _create_public_preset_release(client: TestClient) -> int:
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    create_preset = client.post(
        "/api/v1/agent-presets",
        headers=headers,
        json={
            "slug": "shared-soul",
            "display_name": "Shared Soul",
            "summary": "Shared OpenClaw preset",
            "runtime_family": "openclaw",
            "supported_memory_modes": ["none", "local", "shared"],
            "default_memory_mode": "shared",
            "pinned_skill_dependencies": ["team/search-helper@1.2.0"],
        },
    )
    assert create_preset.status_code == 201, create_preset.text

    preset_id = int(create_preset.json()["id"])
    create_draft = client.post(
        f"/api/v1/agent-presets/{preset_id}/drafts",
        headers=headers,
        json={
            "prompt": "You are the shared soul preset.",
            "model": "gpt-5.4",
            "tools": ["shell"],
        },
    )
    assert create_draft.status_code == 201, create_draft.text
    draft_id = int(create_draft.json()["id"])

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


def test_agent_preset_registry_and_install_planning_expose_memory_variants(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    _prepare_signing_repo(temp_repo_copy, signing_key)
    _configure_env(monkeypatch, tmp_path=tmp_path, repo=temp_repo_copy)
    from server.app import create_app
    from server.worker import run_worker_loop

    client = TestClient(create_app())
    release_id = _create_public_preset_release(client)

    processed = run_worker_loop(limit=1)
    assert processed == 1

    exposure = client.post(
        f"/api/v1/releases/{release_id}/exposures",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
        json={
            "audience_type": "private",
            "listing_mode": "listed",
            "install_mode": "enabled",
            "requested_review_mode": "none",
        },
    )
    assert exposure.status_code == 201, exposure.text

    ai_index = client.get(
        "/registry/ai-index.json",
        headers={"Authorization": "Bearer fixture-maintainer-token"},
    )
    assert ai_index.status_code == 200, ai_index.text
    payload = ai_index.json()
    preset_entry = next(
        item
        for item in payload["skills"]
        if item.get("qualified_name") == "fixture-maintainer/shared-soul"
    )
    assert preset_entry["kind"] == "agent_preset"
    assert preset_entry["supported_memory_modes"] == ["none", "local", "shared"]
    assert preset_entry["default_memory_mode"] == "shared"

    install_plan = plan_from_registry_entry(preset_entry, memory_mode="local")
    assert install_plan["root"]["kind"] == "agent_preset"
    assert install_plan["root"]["selected_memory_mode"] == "local"
    assert install_plan["root"]["default_memory_mode"] == "shared"
    assert install_plan["root"]["supported_memory_modes"] == ["none", "local", "shared"]
