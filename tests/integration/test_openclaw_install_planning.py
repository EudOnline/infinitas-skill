from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.install.service import plan_from_skill_dir


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_skill(path: Path, *, name: str) -> Path:
    skill_dir = path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        skill_dir / "_meta.json",
        {
            "schema_version": 1,
            "name": name,
            "version": "0.3.0",
            "status": "active",
            "summary": "OpenClaw install planning fixture",
            "owner": "fixture-owner",
            "owners": ["fixture-owner"],
            "author": "fixture-owner",
            "review_state": "approved",
            "requires": {
                "tools": ["shell"],
                "env": ["OPENAI_API_KEY"],
                "bins": ["git"],
            },
            "openclaw_runtime": {
                "workspace_scope": "workspace",
                "plugin_capabilities": {"tools": ["shell"], "channels": ["chat"]},
                "background_tasks": {"required": True},
                "subagents": {"required": True},
            },
            "metadata": {
                "openclaw": {
                    "requires": {
                        "bins": ["git"],
                        "env": ["OPENAI_API_KEY"],
                        "config": ["memory.store.enabled"],
                    }
                }
            },
            "depends_on": [],
            "conflicts_with": [],
            "distribution": {"installable": True},
        },
    )
    return skill_dir


def test_install_plan_exposes_openclaw_runtime_target_and_readiness(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path / "skills", name="openclaw-plan-skill")
    target_dir = tmp_path / "workspace" / "skills"
    target_dir.mkdir(parents=True, exist_ok=True)

    plan = plan_from_skill_dir(
        str(skill_dir),
        target_dir=str(target_dir),
        source_registry="self",
        mode="install",
    )

    runtime = plan.get("runtime")
    assert isinstance(runtime, dict), plan
    assert runtime.get("platform") == "openclaw"
    assert runtime.get("install_target", {}).get("path") == str(target_dir.resolve())
    assert runtime.get("workspace_fit", {}).get("status") == "workspace-target"
    assert runtime.get("requires", {}).get("bins") == ["git"]
    assert runtime.get("requires", {}).get("config") == ["memory.store.enabled"]
    assert runtime.get("plugin_needs", {}).get("required", {}).get("tools") == ["shell"]
    assert runtime.get("background_tasks", {}).get("required") is True
    assert runtime.get("subagents", {}).get("required") is True
    assert runtime.get("readiness", {}).get("status")

    assert plan.get("steps"), plan
    root_step = plan["steps"][0]
    assert root_step.get("runtime", {}).get("install_target", {}).get("path") == str(
        target_dir.resolve()
    )


def test_install_plan_without_explicit_target_uses_workspace_default(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path / "skills", name="openclaw-default-target")
    plan = plan_from_skill_dir(
        str(skill_dir),
        source_registry="self",
        mode="install",
    )

    runtime = plan.get("runtime")
    assert isinstance(runtime, dict), plan
    assert runtime.get("platform") == "openclaw"
    assert runtime.get("install_target", {}).get("scope") == "workspace"
    assert runtime.get("install_target", {}).get("path", "").endswith("/skills")
