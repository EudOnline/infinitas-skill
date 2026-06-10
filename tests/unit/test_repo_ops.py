"""Characterization tests for server.repo_ops."""
from __future__ import annotations

import json

import pytest

from server.repo_ops import (
    LockTimeout,
    RepoOpError,
    _normalize_file_content,
    _safe_relative_path,
    locked_repo,
    materialize_submission_skill,
)


class TestSafeRelativePath:
    def test_simple_relative(self):
        result = _safe_relative_path("folder/file.txt")
        assert str(result) == "folder/file.txt"

    def test_absolute_rejected(self):
        with pytest.raises(RepoOpError, match="path must be relative"):
            _safe_relative_path("/etc/passwd")

    def test_parent_traversal_rejected(self):
        with pytest.raises(RepoOpError, match="stay within"):
            _safe_relative_path("../../../etc/passwd")

    def test_current_dir_is_ok(self):
        result = _safe_relative_path("file.txt")
        assert str(result) == "file.txt"


class TestNormalizeFileContent:
    def test_string(self):
        assert _normalize_file_content("hello") == "hello"

    def test_dict(self):
        result = _normalize_file_content({"a": 1})
        parsed = json.loads(result)
        assert parsed == {"a": 1}

    def test_list(self):
        result = _normalize_file_content([1, 2])
        parsed = json.loads(result)
        assert parsed == [1, 2]

    def test_number(self):
        assert _normalize_file_content(42) == "42"


class TestLockedRepo:
    def test_acquires_and_releases(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with locked_repo(lock_file, timeout_seconds=5):
            assert lock_file.exists()
        # Lock should be released after context manager exits

    def test_timeout_on_contended_lock(self, tmp_path):
        lock_file = tmp_path / "test.lock"
        with locked_repo(lock_file, timeout_seconds=5):
            # Try to acquire same lock with a short timeout
            with pytest.raises(LockTimeout):
                with locked_repo(lock_file, timeout_seconds=0.5):
                    pass

    def test_creates_parent_dirs(self, tmp_path):
        lock_file = tmp_path / "nested" / "dir" / "test.lock"
        with locked_repo(lock_file, timeout_seconds=5):
            assert lock_file.parent.exists()


class TestMaterializeSubmissionSkill:
    def test_basic_skill_creation(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        payload = {
            "files": {
                "_meta.json": {"name": "test-skill", "version": "1.0.0"},
                "skill.md": "# Test Skill",
            }
        }
        result = materialize_submission_skill(
            repo,
            skill_name="test-skill",
            payload=payload,
            lock_path=None,
        )
        assert result == repo / "skills" / "incubating" / "test-skill"
        assert (result / "_meta.json").exists()
        assert (result / "skill.md").exists()
        meta = json.loads((result / "_meta.json").read_text(encoding="utf-8"))
        assert meta["status"] == "incubating"

    def test_empty_files_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        with pytest.raises(RepoOpError, match="non-empty files"):
            materialize_submission_skill(
                repo,
                skill_name="test",
                payload={"files": {}},
                lock_path=None,
            )

    def test_missing_meta_json_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        with pytest.raises(RepoOpError, match="_meta.json"):
            materialize_submission_skill(
                repo,
                skill_name="test",
                payload={"files": {"readme.md": "# Hello"}},
                lock_path=None,
            )

    def test_overwrites_existing(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        # First creation
        materialize_submission_skill(
            repo,
            skill_name="skill",
            payload={"files": {"_meta.json": {"name": "skill"}, "old.txt": "old"}},
            lock_path=None,
        )
        # Second creation overwrites
        result = materialize_submission_skill(
            repo,
            skill_name="skill",
            payload={"files": {"_meta.json": {"name": "skill"}, "new.txt": "new"}},
            lock_path=None,
        )
        assert not (result / "old.txt").exists()
        assert (result / "new.txt").exists()

    def test_with_review_payload(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        review = {"status": "pending", "reviewers": ["alice"]}
        result = materialize_submission_skill(
            repo,
            skill_name="skill",
            payload={"files": {"_meta.json": {"name": "skill"}}},
            review_payload=review,
            lock_path=None,
        )
        reviews = json.loads((result / "reviews.json").read_text(encoding="utf-8"))
        assert reviews["status"] == "pending"

    def test_with_namespace_lock(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        lock_path = tmp_path / "repo.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        result = materialize_submission_skill(
            repo,
            skill_name="ns-skill",
            payload={"files": {"_meta.json": {"name": "ns-skill"}}},
            lock_path=lock_path,
        )
        assert result.exists()

    def test_path_traversal_in_file_key_rejected(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        with pytest.raises(RepoOpError, match="stay within"):
            materialize_submission_skill(
                repo,
                skill_name="skill",
                payload={"files": {"_meta.json": {"name": "skill"}, "../escape.txt": "bad"}},
                lock_path=None,
            )
