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
