from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infinitas_skill.release.release_resolution import (
    build_review_payload,
    expected_skill_tag,
    load_json,
    resolve_skill,
)


class TestLoadJson:
    def test_reads_file(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            path.write_text(json.dumps({"a": 1}), encoding="utf-8")
            assert load_json(path) == {"a": 1}


class TestResolveSkill:
    def test_direct_dir(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "_meta.json").write_text("{}", encoding="utf-8")
            assert resolve_skill(td, skill_dir) == skill_dir.resolve()

    def test_in_skills_root(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            skill_dir = root / "skills" / "active" / "my-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "_meta.json").write_text("{}", encoding="utf-8")
            assert resolve_skill(root, "my-skill") == skill_dir.resolve()

    def test_not_found_raises(self):
        with TemporaryDirectory() as td:
            with pytest.raises(Exception) as exc:
                resolve_skill(td, "missing")
            assert "cannot resolve skill" in str(exc.value)


class TestExpectedSkillTag:
    def test_returns_tag(self):
        with TemporaryDirectory() as td:
            skill_dir = Path(td) / "skill"
            skill_dir.mkdir()
            (skill_dir / "_meta.json").write_text(
                json.dumps({"name": "test-skill", "version": "1.0.0"}),
                encoding="utf-8",
            )
            meta, tag = expected_skill_tag(skill_dir)
            assert meta["name"] == "test-skill"
            assert tag == "skill/test-skill/v1.0.0"


class TestBuildReviewPayload:
    def test_empty_entries(self):
        result = build_review_payload([], None)
        assert result == {"reviewers": []}

    def test_with_evaluation(self):
        entries = [{"reviewer": "alice"}]
        evaluation = {
            "effective_review_state": "approved",
            "required_approvals": 1,
            "quorum_met": True,
        }
        result = build_review_payload(entries, evaluation)
        assert result["reviewers"] == entries
        assert result["effective_review_state"] == "approved"
        assert result["quorum_met"] is True
