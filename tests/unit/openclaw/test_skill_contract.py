from __future__ import annotations

import json
from pathlib import Path

import pytest

from infinitas_skill.openclaw.skill_contract import (
    OpenClawSkillContractError,
    load_openclaw_skill_contract,
)
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
    skill_dir = _canonical_skill(
        tmp_path,
        runtime={"plugin_capabilities": {"tools": ["shell"], "channels": ["chat"]}},
    )
    (skill_dir / "SKILL.md").write_text(
        "---\nname: rendered-copy\ndescription: Rendered copy.\n---\n",
        encoding="utf-8",
    )

    payload = load_openclaw_skill_contract(skill_dir)

    assert payload["source_mode"] == "canonical"
    assert payload["source"]["name"] == "canonical-openclaw-skill"
    assert "migration_only" not in payload
    assert payload["runtime"]["requires"] == ["shell-execution", "file-read"]
    assert payload["runtime"]["license"] == "MIT-0"
    assert payload["verification"] == {
        "required_runtimes": ["openclaw"],
        "smoke_prompts": ["run smoke"],
    }


def test_openclaw_contract_accepts_native_skill_directory(tmp_path: Path) -> None:
    skill_dir = tmp_path / "teacher-work-datahub"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: teacher-work-datahub\n"
        "description: Preserve and query teacher work data.\n"
        "---\n\n"
        "# Teacher Work DataHub\n",
        encoding="utf-8",
    )
    (skill_dir / "_meta.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "requires": {
                    "tools": ["read", "exec"],
                    "bins": ["python3"],
                    "env": ["TEACHER_WORK_DATAHUB_ROOT"],
                },
                "distribution": {"installable": True, "channel": "hosted"},
            }
        ),
        encoding="utf-8",
    )

    payload = load_openclaw_skill_contract(skill_dir)

    assert payload["source_mode"] == "openclaw-native"
    assert payload["source"]["name"] == "teacher-work-datahub"
    assert payload["runtime"]["requires"] == [
        "tool:read",
        "tool:exec",
        "bin:python3",
        "env:TEACHER_WORK_DATAHUB_ROOT",
    ]
    assert payload["verification"]["required_runtimes"] == ["openclaw"]


def test_openclaw_native_contract_rejects_missing_description(tmp_path: Path) -> None:
    skill_dir = tmp_path / "incomplete"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: incomplete\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(OpenClawSkillContractError, match="must declare a description"):
        load_openclaw_skill_contract(skill_dir)


def test_render_skill_markdown_does_not_emit_internal_requires_as_runtime_gating(
    tmp_path: Path,
) -> None:
    source = load_skill_source(
        _canonical_skill(tmp_path, runtime={"requires": ["gateway-shell", "workspace-state"]})
    )

    rendered = render_skill_markdown(source, "openclaw", {"platform": "openclaw"})

    assert "metadata.openclaw" not in rendered
    assert "gateway-shell" not in rendered
    assert "workspace-state" not in rendered
