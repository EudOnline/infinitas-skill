from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infinitas_skill.release.git_state import (
    ReleaseError,
    resolve_skill,
    signer_entries,
    split_remote,
)


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
            with pytest.raises(ReleaseError) as exc:
                resolve_skill(td, "missing")
            assert "cannot resolve skill" in str(exc.value)


class TestSignerEntries:
    def test_reads_entries(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "signers"
            path.write_text("alice@example.com\n# comment\nbob@example.com\n", encoding="utf-8")
            assert signer_entries(path) == ["alice@example.com", "bob@example.com"]

    def test_missing_file(self):
        assert signer_entries("/nonexistent") == []


class TestSplitRemote:
    def test_with_slash(self):
        assert split_remote("origin/main", "upstream") == "origin"

    def test_without_slash(self):
        assert split_remote("main", "upstream") == "upstream"

    def test_none_upstream(self):
        assert split_remote(None, "upstream") == "upstream"
