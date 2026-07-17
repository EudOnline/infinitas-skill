from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infinitas_skill.skills.render import (
    RenderSkillError,
    _copy_support_dir,
    apply_tool_intent_mapping,
    load_platform_profile,
    render_skill,
    render_skill_markdown,
)


class TestLoadPlatformProfile:
    def test_loads_valid_profile(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "profiles").mkdir()
            (root / "profiles" / "claude.json").write_text(
                json.dumps({"platform": "claude"}), encoding="utf-8"
            )
            result = load_platform_profile(root, "claude")
            assert result["platform"] == "claude"

    def test_missing_profile_raises(self):
        with TemporaryDirectory() as td:
            with pytest.raises(RenderSkillError) as exc:
                load_platform_profile(Path(td), "claude")
            assert "missing platform profile" in str(exc.value)

    def test_mismatched_platform_raises(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "profiles").mkdir()
            (root / "profiles" / "claude.json").write_text(
                json.dumps({"platform": "codex"}), encoding="utf-8"
            )
            with pytest.raises(RenderSkillError) as exc:
                load_platform_profile(root, "claude")
            assert "mismatched platform" in str(exc.value)


class TestApplyToolIntentMapping:
    def test_maps_required_intents(self):
        source = {"tool_intents": {"required": ["shell_execution"], "optional": []}}
        profile = {"platform": "claude"}
        result = apply_tool_intent_mapping(source, "claude", profile)
        assert result["required"]["shell_execution"] == "Bash"

    def test_maps_optional_intents(self):
        source = {"tool_intents": {"required": [], "optional": ["file_read"]}}
        profile = {"platform": "codex"}
        result = apply_tool_intent_mapping(source, "codex", profile)
        assert result["optional"]["file_read"] == "file tool"

    def test_unknown_platform_passes_through(self):
        source = {"tool_intents": {"required": ["custom"], "optional": []}}
        result = apply_tool_intent_mapping(source, "unknown", {})
        assert result["required"]["custom"] == "custom"


class TestRenderSkillMarkdown:
    def test_basic_render(self):
        with TemporaryDirectory() as td:
            instr_path = Path(td) / "instr.md"
            instr_path.write_text("# Instructions", encoding="utf-8")
            source = {
                "name": "test-skill",
                "description": "A test skill",
                "instructions_body_path": str(instr_path),
                "tool_intents": {"required": [], "optional": []},
                "platform_overrides": {},
            }
            result = render_skill_markdown(source, "claude", {"platform": "claude"})
            assert "test-skill" in result
            assert "# Instructions" in result

    def test_openclaw_render(self):
        with TemporaryDirectory() as td:
            instr_path = Path(td) / "instr.md"
            instr_path.write_text("# Instructions", encoding="utf-8")
            source = {
                "name": "test-skill",
                "description": "A test skill",
                "instructions_body_path": str(instr_path),
                "tool_intents": {"required": ["shell_execution"], "optional": []},
                "platform_overrides": {},
                "openclaw_runtime": {},
                "distribution": {"license": "MIT"},
            }
            result = render_skill_markdown(source, "openclaw", {"platform": "openclaw"})
            assert "metadata.openclaw.requires" in result
            assert "MIT" in result

    def test_tool_mapping_section(self):
        with TemporaryDirectory() as td:
            instr_path = Path(td) / "instr.md"
            instr_path.write_text("# Instructions", encoding="utf-8")
            source = {
                "name": "test-skill",
                "description": "A test skill",
                "instructions_body_path": str(instr_path),
                "tool_intents": {"required": ["shell_execution"], "optional": ["file_read"]},
                "platform_overrides": {},
            }
            result = render_skill_markdown(source, "claude", {"platform": "claude"})
            assert "## Platform Tool Mapping" in result
            assert "Required intents:" in result
            assert "Optional intents:" in result
            assert "`shell_execution` -> `Bash`" in result


class TestCopySupportDir:
    def test_copies_directory(self):
        with TemporaryDirectory() as td:
            source = Path(td) / "src"
            target = Path(td) / "out"
            (source / "references").mkdir(parents=True)
            (source / "references" / "ref.md").write_text("ref", encoding="utf-8")
            files = _copy_support_dir(source, target, "references")
            assert any("references/ref.md" in f for f in files)

    def test_missing_dir_returns_empty(self):
        with TemporaryDirectory() as td:
            source = Path(td) / "src"
            target = Path(td) / "out"
            assert _copy_support_dir(source, target, "missing") == []


class TestRenderSkill:
    def test_render_canonical(self):
        with TemporaryDirectory() as td:
            source_dir = Path(td) / "skill"
            source_dir.mkdir()
            instr = source_dir / "instr.md"
            instr.write_text("# Instructions", encoding="utf-8")
            (source_dir / "references").mkdir()
            (source_dir / "references" / "ref.md").write_text("ref", encoding="utf-8")
            source = {
                "name": "test-skill",
                "description": "A test skill",
                "instructions_body_path": str(instr),
                "tool_intents": {"required": [], "optional": []},
                "platform_overrides": {},
                "source_dir": str(source_dir),
                "source_mode": "canonical",
            }
            out_dir = Path(td) / "out"
            result = render_skill(source, "claude", out_dir, {"platform": "claude"})
            assert result["platform"] == "claude"
            assert "SKILL.md" in result["files"]
            assert (out_dir / "SKILL.md").exists()

    @pytest.mark.parametrize(
        ("platform", "overrides", "expected_file"),
        [
            ("claude", {"command_wrapper_name": "test-skill"}, "commands/test-skill.md"),
            ("codex", {"emit_openai_yaml": True}, "agents/openai.yaml"),
            ("codex", {"emit_agents_md_snippet": True}, "AGENTS.md"),
        ],
    )
    def test_render_emits_platform_overlay_files(
        self, platform: str, overrides: dict, expected_file: str
    ) -> None:
        with TemporaryDirectory() as td:
            source_dir = Path(td) / "skill"
            source_dir.mkdir()
            instructions = source_dir / "instructions.md"
            instructions.write_text("# Instructions", encoding="utf-8")
            source = {
                "name": "test-skill",
                "description": "A test skill",
                "instructions_body_path": str(instructions),
                "tool_intents": {"required": [], "optional": []},
                "platform_overrides": {platform: overrides},
                "source_dir": str(source_dir),
                "source_mode": "canonical",
            }
            out_dir = Path(td) / "out"

            result = render_skill(source, platform, out_dir, {"platform": platform})

            assert expected_file in result["files"]
            assert (out_dir / expected_file).is_file()
