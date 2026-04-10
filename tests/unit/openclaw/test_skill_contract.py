from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.openclaw.skill_contract import load_openclaw_skill_contract
from infinitas_skill.skills.canonical import load_skill_source
from infinitas_skill.skills.render import load_platform_profile, render_skill_markdown


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_openclaw_skill_contract_marks_legacy_inputs_as_migration_only(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "legacy-skill"
    _write(
        skill_dir / "_meta.json",
        json.dumps(
            {
                "schema_version": 1,
                "name": "legacy-openclaw-skill",
                "summary": "legacy summary",
                "distribution": {},
                "tests": {},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    _write(
        skill_dir / "SKILL.md",
        "---\n"
        "name: Legacy OpenClaw Skill\n"
        "description: Legacy bridge fixture\n"
        "metadata.openclaw.requires: shell, file-access\n"
        "---\n\n"
        "Legacy body.\n",
    )

    payload = load_openclaw_skill_contract(skill_dir)

    assert payload["platform"] == "openclaw"
    assert payload["source_mode"] == "legacy-migration"
    assert payload["migration_only"] is True
    assert payload["runtime"]["requires"] == ["shell", "file-access"]
    assert payload["verification"] == {
        "required_runtimes": [],
        "smoke_prompts": [],
        "legacy": {
            "required_platforms": [],
            "required_platforms_deprecated": True,
        },
    }


def test_load_skill_source_exposes_openclaw_runtime_fields_when_present(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "canonical-skill"
    _write(skill_dir / "BODY.md", "Canonical body.\n")
    _write(
        skill_dir / "skill.json",
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
                    "required_platforms": ["openclaw"],
                },
                "openclaw_runtime": {
                    "workspace_scope": "workspace",
                    "plugin_capabilities": {"tools": ["shell"], "channels": ["chat"]},
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    source = load_skill_source(skill_dir)

    assert source["source_mode"] == "canonical"
    assert source["openclaw_runtime"]["workspace_scope"] == "workspace"
    assert source["runtime_verification"] == {
        "required_runtimes": ["openclaw"],
        "smoke_prompts": [],
        "required_platforms_legacy": ["openclaw"],
        "required_platforms_deprecated": True,
    }
    assert source["openclaw_runtime"]["plugin_capabilities"] == {
        "tools": ["shell"],
        "channels": ["chat"],
    }


def test_load_openclaw_skill_contract_builds_native_runtime_from_canonical_source(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "canonical-skill"
    _write(skill_dir / "BODY.md", "Canonical body.\n")
    _write(
        skill_dir / "skill.json",
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
                    "required_platforms": ["openclaw"],
                },
                "distribution": {"license": "MIT-0"},
                "openclaw_runtime": {
                    "plugin_capabilities": {"tools": ["shell"], "channels": ["chat"]},
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    payload = load_openclaw_skill_contract(skill_dir)

    assert payload["source_mode"] == "canonical"
    assert payload["migration_only"] is False
    assert payload["runtime"]["requires"] == ["shell-execution", "file-read"]
    assert payload["runtime"]["plugin_capabilities"] == {
        "tools": ["shell"],
        "channels": ["chat"],
    }
    assert payload["runtime"]["license"] == "MIT-0"
    assert payload["verification"] == {
        "required_runtimes": ["openclaw"],
        "smoke_prompts": [],
        "legacy": {
            "required_platforms": ["openclaw"],
            "required_platforms_deprecated": True,
        },
    }


def test_load_skill_source_accepts_required_runtimes_alias_for_canonical_verification(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "canonical-skill"
    _write(skill_dir / "BODY.md", "Canonical body.\n")
    _write(
        skill_dir / "skill.json",
        json.dumps(
            {
                "schema_version": 1,
                "name": "canonical-openclaw-skill",
                "summary": "summary",
                "description": "description",
                "instructions_body": "BODY.md",
                "tool_intents": {
                    "required": ["shell_execution"],
                    "optional": [],
                },
                "verification": {
                    "required_runtimes": ["openclaw"],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    source = load_skill_source(skill_dir)

    assert source["verification"] == {
        "required_platforms": ["openclaw"],
        "required_runtimes": ["openclaw"],
        "smoke_prompts": [],
        "required_platforms_deprecated": False,
    }
    assert source["runtime_verification"] == {
        "required_runtimes": ["openclaw"],
        "smoke_prompts": [],
        "required_platforms_legacy": ["openclaw"],
        "required_platforms_deprecated": True,
    }

    payload = load_openclaw_skill_contract(skill_dir)
    assert payload["verification"] == {
        "required_runtimes": ["openclaw"],
        "smoke_prompts": [],
        "legacy": {
            "required_platforms": ["openclaw"],
            "required_platforms_deprecated": False,
        },
    }


def test_render_skill_markdown_prefers_openclaw_runtime_requires(
    tmp_path: Path,
) -> None:
    skill_dir = tmp_path / "canonical-skill"
    _write(skill_dir / "BODY.md", "Canonical body.\n")
    _write(
        skill_dir / "skill.json",
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
                    "required_platforms": ["openclaw"],
                },
                "openclaw_runtime": {
                    "requires": ["gateway-shell", "workspace-state"],
                },
                "platform_overrides": {
                    "openclaw": {
                        "requires": ["legacy-rendered"],
                    }
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    source = load_skill_source(skill_dir)
    profile = load_platform_profile(Path(__file__).resolve().parents[3], "openclaw")
    skill_md = render_skill_markdown(source, "openclaw", profile)

    assert "metadata.openclaw.requires: gateway-shell, workspace-state" in skill_md
