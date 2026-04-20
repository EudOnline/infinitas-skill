from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


def configure_env(tmpdir: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "test-secret-key"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(
        [
            {
                "username": "fixture-maintainer",
                "display_name": "Fixture Maintainer",
                "role": "maintainer",
                "token": "fixture-maintainer-token",
            }
        ]
    )


def test_agent_preset_create_draft_and_seal_flow() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-agent-preset-api-test-"))
    try:
        configure_env(tmpdir)

        from server.app import create_app

        client = TestClient(create_app())
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
                "pinned_skill_dependencies": ["team/search-helper@1.2.0"],
            },
        )
        assert create_preset.status_code == 201, create_preset.text
        preset_payload = create_preset.json()
        assert preset_payload["slug"] == "shared-soul"
        assert preset_payload["runtime_family"] == "openclaw"
        assert preset_payload["supported_memory_modes"] == ["local", "shared"]
        assert preset_payload["default_memory_mode"] == "shared"
        assert preset_payload["pinned_skill_dependencies"] == ["team/search-helper@1.2.0"]

        preset_id = int(preset_payload["id"])
        create_draft = client.post(
            f"/api/v1/agent-presets/{preset_id}/drafts",
            headers=headers,
            json={
                "prompt": "You are the shared soul preset.",
                "model": "gpt-5.4",
                "tools": ["shell", "search"],
            },
        )
        assert create_draft.status_code == 201, create_draft.text
        draft_payload = create_draft.json()
        assert draft_payload["content_mode"] == "uploaded_bundle"
        assert draft_payload["content_artifact_id"] is not None

        draft_id = int(draft_payload["id"])
        seal = client.post(
            f"/api/v1/agent-preset-drafts/{draft_id}/seal",
            headers=headers,
            json={"version": "0.1.0"},
        )
        assert seal.status_code == 201, seal.text
        seal_payload = seal.json()
        version_payload = seal_payload["skill_version"]
        assert version_payload["version"] == "0.1.0"
        assert version_payload["sealed_manifest"]["metadata"]["kind"] == "agent_preset"
        assert version_payload["sealed_manifest"]["metadata"]["runtime_family"] == "openclaw"
        assert version_payload["sealed_manifest"]["metadata"]["supported_memory_modes"] == [
            "local",
            "shared",
        ]
        assert version_payload["sealed_manifest"]["metadata"]["default_memory_mode"] == "shared"
        assert version_payload["sealed_manifest"]["metadata"]["pinned_skill_dependencies"] == [
            "team/search-helper@1.2.0"
        ]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
