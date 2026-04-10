from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.openclaw.contracts import load_openclaw_runtime_profile
from infinitas_skill.openclaw.runtime_model import build_openclaw_runtime_model

ROOT = Path(__file__).resolve().parents[3]


def test_openclaw_profile_exposes_native_runtime_capabilities() -> None:
    profile = load_openclaw_runtime_profile(ROOT)

    assert profile["platform"] == "openclaw"
    assert profile["capabilities"]["supports_subagents"] is True
    assert profile["capabilities"]["supports_plugins"] is True
    assert profile["capabilities"]["supports_background_tasks"] is True
    assert profile["capabilities"]["supports_cron_jobs"] is True


def test_build_openclaw_runtime_model_keeps_contract_metadata() -> None:
    model = build_openclaw_runtime_model(ROOT)

    assert model["platform"] == "openclaw"
    assert model["entrypoint"] == "SKILL.md"
    assert model["contract_last_verified"] == "2026-04-07"
    assert model["skill_dir_candidates"] == [
        "skills",
        ".agents/skills",
        "~/.agents/skills",
        "~/.openclaw/skills",
    ]


def test_build_openclaw_runtime_model_normalizes_profile_plugin_capabilities(
    tmp_path: Path,
) -> None:
    profile = load_openclaw_runtime_profile(ROOT)
    profile["constraints"]["plugin_capabilities"] = {
        "channels": ["chat"],
        "tools": ["shell", "edit"],
        "ignored_flag": True,
    }
    profile_root = tmp_path / "repo"
    (profile_root / "profiles").mkdir(parents=True)
    (profile_root / "profiles" / "openclaw.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    model = build_openclaw_runtime_model(profile_root)

    assert model["plugin_capabilities"] == {
        "channels": ["chat"],
        "tools": ["shell", "edit"],
    }
