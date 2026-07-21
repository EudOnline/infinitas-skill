from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infinitas_skill.skills import openclaw
from src.infinitas_skill.skills.openclaw import (
    OpenClawBridgeError,
    _strip_quotes,
    derive_registry_meta,
    export_release_to_directory,
    parse_skill_frontmatter,
    resolve_skill_dir,
    scaffold_imported_skill,
    select_ai_skill,
    slugify,
    validate_exported_openclaw_dir,
)


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_multiple_spaces(self):
        assert slugify("Hello   World") == "hello-world"

    def test_special_chars(self):
        assert slugify("Hello@World#Test") == "hello-world-test"

    def test_leading_trailing_dashes(self):
        assert slugify("---hello---") == "hello"

    def test_empty(self):
        assert slugify("") == ""

    def test_none(self):
        assert slugify(None) == ""


class TestStripQuotes:
    def test_double_quotes(self):
        assert _strip_quotes('"hello"') == "hello"

    def test_single_quotes(self):
        assert _strip_quotes("'hello'") == "hello"

    def test_no_quotes(self):
        assert _strip_quotes("hello") == "hello"

    def test_whitespace(self):
        assert _strip_quotes('  "hello"  ') == "hello"


class TestResolveSkillDir:
    def test_valid_dir(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Skill", encoding="utf-8")
            assert resolve_skill_dir(str(skill_dir)) == skill_dir.resolve()

    def test_from_skill_md_file(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text("# Skill", encoding="utf-8")
            assert resolve_skill_dir(str(skill_md)) == skill_dir.resolve()

    def test_missing_skill_md(self):
        with TemporaryDirectory() as td:
            with pytest.raises(OpenClawBridgeError) as exc:
                resolve_skill_dir(td)
            assert "missing SKILL.md" in str(exc.value)

    def test_not_a_dir(self):
        with TemporaryDirectory() as td:
            with pytest.raises(OpenClawBridgeError) as exc:
                resolve_skill_dir(str(Path(td) / "nonexistent"))
            assert "not a skill directory" in str(exc.value)


class TestParseSkillFrontmatter:
    def test_parses_valid_frontmatter(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "SKILL.md"
            path.write_text('---\nname: "Test Skill"\ndescription: "A test"\n---\n# Body')
            result = parse_skill_frontmatter(path)
            assert result["name"] == "Test Skill"
            assert result["description"] == "A test"

    def test_missing_frontmatter_raises(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "SKILL.md"
            path.write_text("# No frontmatter")
            with pytest.raises(OpenClawBridgeError) as exc:
                parse_skill_frontmatter(path)
            assert "missing YAML frontmatter" in str(exc.value)

    def test_missing_name_raises(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "SKILL.md"
            path.write_text('---\ndescription: "A test"\n---\n# Body')
            with pytest.raises(OpenClawBridgeError) as exc:
                parse_skill_frontmatter(path)
            assert "missing frontmatter name" in str(exc.value)

    def test_missing_description_raises(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "SKILL.md"
            path.write_text('---\nname: "Test"\n---\n# Body')
            with pytest.raises(OpenClawBridgeError) as exc:
                parse_skill_frontmatter(path)
            assert "missing frontmatter description" in str(exc.value)


class TestDeriveRegistryMeta:
    def test_basic(self):
        result = derive_registry_meta({"name": "Test Skill", "description": "A test"}, "alice")
        assert result["name"] == "test-skill"
        assert result["owner"] == "alice"
        assert result["status"] == "incubating"
        assert "publisher" not in result

    def test_with_publisher(self):
        result = derive_registry_meta(
            {"name": "Test Skill", "description": "A test"}, "alice", "acme"
        )
        assert result["publisher"] == "acme"
        assert result["qualified_name"] == "acme/test-skill"

    def test_empty_owner_raises(self):
        with pytest.raises(OpenClawBridgeError) as exc:
            derive_registry_meta({"name": "Test", "description": "A test"}, "")
        assert "owner must be non-empty" in str(exc.value)

    def test_empty_name_raises(self):
        with pytest.raises(OpenClawBridgeError) as exc:
            derive_registry_meta({"name": "", "description": "A test"}, "alice")
        assert "does not produce a valid registry slug" in str(exc.value)


class TestScaffoldImportedSkill:
    def test_scaffold(self):
        with TemporaryDirectory() as td:
            source = Path(td) / "source"
            target = Path(td) / "target"
            source.mkdir()
            (source / "SKILL.md").write_text("# Skill", encoding="utf-8")
            meta = {"name": "test-skill"}
            result = scaffold_imported_skill(source, target, meta)
            assert target.exists()
            assert (target / "_meta.json").exists()
            assert (target / "reviews.json").exists()
            assert (target / "tests" / "smoke.md").exists()
            assert result["meta"] == meta

    def test_target_exists_raises(self):
        with TemporaryDirectory() as td:
            source = Path(td) / "source"
            target = Path(td) / "target"
            source.mkdir()
            target.mkdir()
            with pytest.raises(OpenClawBridgeError) as exc:
                scaffold_imported_skill(source, target, {})
            assert "target already exists" in str(exc.value)

    def test_force_overwrite(self):
        with TemporaryDirectory() as td:
            source = Path(td) / "source"
            target = Path(td) / "target"
            source.mkdir()
            target.mkdir()
            (source / "SKILL.md").write_text("# Skill", encoding="utf-8")
            scaffold_imported_skill(source, target, {}, force=True)
            assert (target / "SKILL.md").exists()


class TestSelectAiSkill:
    def test_by_qualified_name(self):
        ai_index = {
            "skills": [
                {"qualified_name": "acme/skill1", "name": "skill1"},
                {"qualified_name": "acme/skill2", "name": "skill2"},
            ]
        }
        result = select_ai_skill(ai_index, "acme/skill1")
        assert result["qualified_name"] == "acme/skill1"

    def test_by_name(self):
        ai_index = {
            "skills": [
                {"qualified_name": "acme/skill1", "name": "skill1"},
            ]
        }
        result = select_ai_skill(ai_index, "skill1")
        assert result["name"] == "skill1"

    def test_not_found_raises(self):
        with pytest.raises(OpenClawBridgeError) as exc:
            select_ai_skill({"skills": []}, "missing")
        assert "no AI-index entry found" in str(exc.value)

    def test_ambiguous_raises(self):
        ai_index = {
            "skills": [
                {"qualified_name": "acme/skill", "name": "skill"},
                {"qualified_name": "other/skill", "name": "skill"},
            ]
        }
        with pytest.raises(OpenClawBridgeError) as exc:
            select_ai_skill(ai_index, "skill")
        assert "ambiguous" in str(exc.value)


class TestValidateExportedOpenclawDir:
    def test_valid_dir(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                '---\nname: "Test"\ndescription: "A test"\n---\n# Body',
                encoding="utf-8",
            )
            result = validate_exported_openclaw_dir(skill_dir)
            assert result["ok"] is True

    def test_missing_skill_md(self):
        with TemporaryDirectory() as td:
            result = validate_exported_openclaw_dir(Path(td))
            assert result["ok"] is False
            assert any("missing SKILL.md" in e for e in result["errors"])

    def test_runtime_metadata_is_optional(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                '---\nname: "Test"\ndescription: "A test"\n---\n# Body',
                encoding="utf-8",
            )
            result = validate_exported_openclaw_dir(skill_dir)
            assert result["ok"] is True

    def test_public_ready_does_not_require_license_metadata(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                '---\nname: "Test"\ndescription: "A test"\n---\n# Body',
                encoding="utf-8",
            )
            result = validate_exported_openclaw_dir(skill_dir, public_ready=True)
            assert result["ok"] is True
            assert result["public_ready"] is True

    def test_public_ready_size_check(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                '---\nname: "Test"\ndescription: "A test"\n---\n# Body',
                encoding="utf-8",
            )
            result = validate_exported_openclaw_dir(skill_dir, public_ready=True)
            assert result["ok"] is True
            assert result["public_ready"] is True

    def test_public_ready_allows_binary_assets(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                '---\nname: "Test"\ndescription: "A test"\n---\n# Body',
                encoding="utf-8",
            )
            (skill_dir / "asset.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            result = validate_exported_openclaw_dir(skill_dir, public_ready=True)

            assert result["ok"] is True
            assert result["public_ready"] is True


class TestExportReleaseToDirectory:
    def test_copies_rendered_release_bundle_and_validates_it(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "rendered-release"
        source_dir.mkdir()
        (source_dir / "SKILL.md").write_text(
            "---\nname: rendered-release\ndescription: Rendered fixture.\n---\n# Body",
            encoding="utf-8",
        )
        (source_dir / "asset.bin").write_bytes(b"\x00binary")

        monkeypatch.setattr(
            openclaw,
            "materialize_distribution_source",
            lambda *_args, **_kwargs: {
                "materialized_path": str(source_dir),
                "cleanup_dir": None,
            },
        )

        result = export_release_to_directory(
            tmp_path,
            tmp_path / "manifest.json",
            tmp_path / "export",
            public_ready=True,
        )

        assert result["migration_contract_source_mode"] == "rendered-release"
        assert result["public_ready"] is True
        assert (tmp_path / "export" / "SKILL.md").is_file()
        assert (tmp_path / "export" / "asset.bin").read_bytes() == b"\x00binary"
