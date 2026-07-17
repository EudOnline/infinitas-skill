from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.openclaw.skill_contract import load_openclaw_skill_contract
from infinitas_skill.skills.canonical import load_skill_source
from infinitas_skill.skills.render import render_skill_markdown


def _canonical_skill(tmp_path: Path, *, runtime: dict | None = None) -> Path:
    skill_dir = tmp_path / "canonical-skill"
    skill_dir.mkdir()
    (skill_dir / "BODY.md").write_text("Canonical body.\n", encoding="utf-8")
    (skill_dir / "skill.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "name": "canonical-openclaw-skill",
                "summary": "summary",
                "description": "description",
                "instructions_body": "BODY.md",
                "tool_intents": {
                    "required": ["shell_execution", "file_read"],
                    "optional": [],
                },
                "verification": {
                    "required_runtimes": ["openclaw"],
                    "smoke_prompts": ["run smoke"],
                },
                "distribution": {"license": "MIT-0"},
                "openclaw_runtime": runtime or {},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return skill_dir


def test_load_skill_source_exposes_only_current_verification_contract(tmp_path: Path) -> None:
    source = load_skill_source(_canonical_skill(tmp_path))

    assert source["verification"] == {
        "required_runtimes": ["openclaw"],
        "smoke_prompts": ["run smoke"],
    }
    assert "runtime_verification" not in source


def test_openclaw_contract_builds_runtime_from_canonical_source(tmp_path: Path) -> None:
    payload = load_openclaw_skill_contract(
        _canonical_skill(
            tmp_path,
            runtime={"plugin_capabilities": {"tools": ["shell"], "channels": ["chat"]}},
        )
    )

    assert payload["source_mode"] == "canonical"
    assert "migration_only" not in payload
    assert payload["runtime"]["requires"] == ["shell-execution", "file-read"]
    assert payload["runtime"]["license"] == "MIT-0"
    assert payload["verification"] == {
        "required_runtimes": ["openclaw"],
        "smoke_prompts": ["run smoke"],
    }


def test_render_skill_markdown_prefers_explicit_openclaw_requires(tmp_path: Path) -> None:
    source = load_skill_source(
        _canonical_skill(tmp_path, runtime={"requires": ["gateway-shell", "workspace-state"]})
    )

    rendered = render_skill_markdown(source, "openclaw", {"platform": "openclaw"})

    assert "metadata.openclaw.requires: gateway-shell, workspace-state" in rendered
