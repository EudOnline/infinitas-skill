from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infinitas_skill.skills.canonical import (
    CanonicalSkillError,
    _legacy_openclaw_runtime,
    _normalized_verification_payload,
    _runtime_verification_alias,
    _split_frontmatter_list,
    is_canonical_skill_dir,
    is_legacy_skill_dir,
    load_canonical_skill,
    load_legacy_skill,
    load_skill_source,
    parse_skill_frontmatter,
    validate_canonical_payload,
)


class TestSplitFrontmatterList:
    def test_splits_comma_separated(self):
        assert _split_frontmatter_list("a, b, c") == ["a", "b", "c"]

    def test_deduplicates(self):
        assert _split_frontmatter_list("a, a, b") == ["a", "b"]

    def test_empty_string(self):
        assert _split_frontmatter_list("") == []

    def test_none(self):
        assert _split_frontmatter_list(None) == []

    def test_whitespace_only(self):
        assert _split_frontmatter_list("   ") == []


class TestNormalizedVerificationPayload:
    def test_empty(self):
        result = _normalized_verification_payload({})
        assert result["required_platforms"] == []
        assert result["required_runtimes"] == []
        assert result["smoke_prompts"] == []
        assert result["required_platforms_deprecated"] is False

    def test_with_required_runtimes(self):
        result = _normalized_verification_payload({"required_runtimes": ["python3.11"]})
        assert result["required_runtimes"] == ["python3.11"]
        assert result["required_platforms_deprecated"] is False

    def test_with_required_platforms(self):
        result = _normalized_verification_payload({"required_platforms": ["python3.11"]})
        assert result["required_platforms"] == ["python3.11"]
        assert result["required_platforms_deprecated"] is True

    def test_with_smoke_prompts(self):
        result = _normalized_verification_payload({"smoke_prompts": ["test"]})
        assert result["smoke_prompts"] == ["test"]


class TestRuntimeVerificationAlias:
    def test_empty(self):
        result = _runtime_verification_alias({})
        assert result["required_runtimes"] == []
        assert result["smoke_prompts"] == []
        assert result["required_platforms_deprecated"] is True

    def test_with_values(self):
        result = _runtime_verification_alias(
            {
                "required_platforms": ["py311"],
                "smoke_prompts": ["hello"],
            }
        )
        assert result["required_runtimes"] == ["py311"]
        assert result["smoke_prompts"] == ["hello"]


class TestLegacyOpenclawRuntime:
    def test_empty(self):
        assert _legacy_openclaw_runtime({}) == {}

    def test_with_requires(self):
        result = _legacy_openclaw_runtime({"metadata.openclaw.requires": "a, b"})
        assert result["requires"] == ["a", "b"]

    def test_with_license(self):
        result = _legacy_openclaw_runtime({"metadata.openclaw.license": "MIT"})
        assert result["license"] == "MIT"

    def test_both_empty(self):
        assert _legacy_openclaw_runtime({"metadata.openclaw.requires": ""}) == {}


class TestValidateCanonicalPayload:
    def test_valid_payload(self):
        payload = {
            "schema_version": 1,
            "name": "test-skill",
            "summary": "A test skill",
            "description": "Description",
            "instructions_body": "instructions.md",
            "tool_intents": {"required": ["read"], "optional": []},
            "verification": {"required_runtimes": ["python3.11"], "smoke_prompts": []},
        }
        assert validate_canonical_payload(payload) == []

    def test_missing_fields(self):
        errors = validate_canonical_payload({})
        assert any("missing required canonical field" in e for e in errors)

    def test_invalid_name(self):
        payload = {
            "schema_version": 1,
            "name": "Bad Name!",
            "summary": "s",
            "description": "d",
            "instructions_body": "i.md",
            "tool_intents": {"required": [], "optional": []},
            "verification": {"required_runtimes": [], "smoke_prompts": []},
        }
        errors = validate_canonical_payload(payload)
        assert any("invalid canonical name" in e for e in errors)

    def test_non_dict_payload(self):
        errors = validate_canonical_payload("not a dict")
        assert any("must be an object" in e for e in errors)

    def test_empty_strings(self):
        payload = {
            "schema_version": 1,
            "name": "test-skill",
            "summary": "",
            "description": "d",
            "instructions_body": "i.md",
            "tool_intents": {"required": [], "optional": []},
            "verification": {"required_runtimes": [], "smoke_prompts": []},
        }
        errors = validate_canonical_payload(payload)
        assert any("summary must be a non-empty string" in e for e in errors)

    def test_bad_tool_intents(self):
        payload = {
            "schema_version": 1,
            "name": "test-skill",
            "summary": "s",
            "description": "d",
            "instructions_body": "i.md",
            "tool_intents": "bad",
            "verification": {"required_runtimes": [], "smoke_prompts": []},
        }
        errors = validate_canonical_payload(payload)
        assert any("tool_intents must be an object" in e for e in errors)

    def test_bad_verification(self):
        payload = {
            "schema_version": 1,
            "name": "test-skill",
            "summary": "s",
            "description": "d",
            "instructions_body": "i.md",
            "tool_intents": {"required": [], "optional": []},
            "verification": "bad",
        }
        errors = validate_canonical_payload(payload)
        assert any("verification must be an object" in e for e in errors)

    def test_optional_fields_bad_types(self):
        payload = {
            "schema_version": 1,
            "name": "test-skill",
            "summary": "s",
            "description": "d",
            "instructions_body": "i.md",
            "tool_intents": {"required": [], "optional": []},
            "verification": {"required_runtimes": [], "smoke_prompts": []},
            "distribution": "bad",
            "degrades_to": "bad",
            "openclaw_runtime": "bad",
        }
        errors = validate_canonical_payload(payload)
        assert any("distribution must be an object" in e for e in errors)
        assert any("degrades_to must be an object" in e for e in errors)
        assert any("openclaw_runtime must be an object" in e for e in errors)


class TestSkillDirChecks:
    def test_is_canonical_skill_dir(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "skill"
            path.mkdir()
            (path / "skill.json").write_text("{}")
            assert is_canonical_skill_dir(path) is True
            assert is_legacy_skill_dir(path) is False

    def test_is_legacy_skill_dir(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "skill"
            path.mkdir()
            (path / "_meta.json").write_text("{}")
            (path / "SKILL.md").write_text("# Skill")
            assert is_legacy_skill_dir(path) is True
            assert is_canonical_skill_dir(path) is False

    def test_not_a_skill_dir(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "empty"
            path.mkdir()
            assert is_canonical_skill_dir(path) is False
            assert is_legacy_skill_dir(path) is False


class TestParseSkillFrontmatter:
    def test_parses_frontmatter(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "SKILL.md"
            path.write_text('---\nname: "Test"\ndescription: Hello\n---\n# Body')
            result = parse_skill_frontmatter(path)
            assert result["name"] == "Test"
            assert result["description"] == "Hello"

    def test_missing_frontmatter_raises(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "SKILL.md"
            path.write_text("# No frontmatter")
            with pytest.raises(CanonicalSkillError) as exc:
                parse_skill_frontmatter(path)
            assert "missing YAML frontmatter" in str(exc.value)

    def test_skips_comments_and_empty_lines(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "SKILL.md"
            path.write_text("---\n# comment\n\nkey: value\n---\n")
            result = parse_skill_frontmatter(path)
            assert result["key"] == "value"


class TestLoadCanonicalSkill:
    def test_loads_valid_skill(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "skill.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "test-skill",
                        "summary": "A test",
                        "description": "Desc",
                        "instructions_body": "instr.md",
                        "tool_intents": {"required": [], "optional": []},
                        "verification": {"required_runtimes": [], "smoke_prompts": []},
                    }
                )
            )
            (skill_dir / "instr.md").write_text("# Instructions")
            result = load_canonical_skill(skill_dir)
            assert result["name"] == "test-skill"
            assert result["source_mode"] == "canonical"

    def test_missing_skill_json_raises(self):
        with TemporaryDirectory() as td:
            with pytest.raises(CanonicalSkillError) as exc:
                load_canonical_skill(Path(td))
            assert "missing skill.json" in str(exc.value)

    def test_missing_instructions_raises(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "skill.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "test-skill",
                        "summary": "A test",
                        "description": "Desc",
                        "instructions_body": "missing.md",
                        "tool_intents": {"required": [], "optional": []},
                        "verification": {"required_runtimes": [], "smoke_prompts": []},
                    }
                )
            )
            with pytest.raises(CanonicalSkillError) as exc:
                load_canonical_skill(skill_dir)
            assert "missing canonical instructions" in str(exc.value)


class TestLoadLegacySkill:
    def test_loads_valid_legacy_skill(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "_meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "legacy-skill",
                        "summary": "Legacy",
                    }
                )
            )
            (skill_dir / "SKILL.md").write_text('---\ndescription: "Legacy desc"\n---\n# Body')
            result = load_legacy_skill(skill_dir)
            assert result["name"] == "legacy-skill"
            assert result["source_mode"] == "legacy"

    def test_missing_files_raises(self):
        with TemporaryDirectory() as td:
            with pytest.raises(CanonicalSkillError) as exc:
                load_legacy_skill(Path(td))
            assert "missing legacy skill files" in str(exc.value)


class TestLoadSkillSource:
    def test_prefers_canonical(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "skill.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "test-skill",
                        "summary": "A test",
                        "description": "Desc",
                        "instructions_body": "instr.md",
                        "tool_intents": {"required": [], "optional": []},
                        "verification": {"required_runtimes": [], "smoke_prompts": []},
                    }
                )
            )
            (skill_dir / "instr.md").write_text("# Instructions")
            result = load_skill_source(skill_dir)
            assert result["source_mode"] == "canonical"

    def test_falls_back_to_legacy(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "_meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "legacy-skill",
                        "summary": "Legacy",
                    }
                )
            )
            (skill_dir / "SKILL.md").write_text('---\ndescription: "Legacy desc"\n---\n# Body')
            result = load_skill_source(skill_dir)
            assert result["source_mode"] == "legacy"

    def test_unsupported_layout_raises(self):
        with TemporaryDirectory() as td:
            with pytest.raises(CanonicalSkillError) as exc:
                load_skill_source(Path(td))
            assert "unsupported skill source layout" in str(exc.value)
