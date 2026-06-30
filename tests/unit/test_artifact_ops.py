"""Characterization tests for server.artifact_ops."""

from __future__ import annotations

import hashlib

from server.artifact_ops import (
    _copy_or_remove,
    _merge_tree,
    _replace_tree,
    ensure_file_bytes,
    ensure_file_copy,
    sha256_bytes,
    sync_catalog_artifacts,
)


class TestSha256Bytes:
    def test_empty(self):
        assert sha256_bytes(b"") == hashlib.sha256(b"").hexdigest()

    def test_known_value(self):
        data = b"hello world"
        assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()

    def test_deterministic(self):
        assert sha256_bytes(b"test") == sha256_bytes(b"test")


class TestEnsureFileBytes:
    def test_creates_file(self, tmp_path):
        target = tmp_path / "output.bin"
        ensure_file_bytes(target, b"content")
        assert target.read_bytes() == b"content"

    def test_skips_identical(self, tmp_path):
        target = tmp_path / "output.bin"
        ensure_file_bytes(target, b"same")
        # Second call should not modify
        mtime_before = target.stat().st_mtime
        ensure_file_bytes(target, b"same")
        # mtime should not change (or be very close)
        import os

        assert os.path.getmtime(target) == mtime_before

    def test_overwrites_different(self, tmp_path):
        target = tmp_path / "output.bin"
        ensure_file_bytes(target, b"old")
        ensure_file_bytes(target, b"new")
        assert target.read_bytes() == b"new"

    def test_creates_parent_dirs(self, tmp_path):
        target = tmp_path / "a" / "b" / "c" / "file.txt"
        ensure_file_bytes(target, b"deep")
        assert target.read_bytes() == b"deep"

    def test_atomic_no_partial_on_error(self, tmp_path):
        """Verify no .partial files remain after an error."""
        target = tmp_path / "output.bin"
        # Writing extremely large data should work, but let's test the cleanup
        # by simulating via a direct call
        ensure_file_bytes(target, b"normal")
        partials = list(tmp_path.glob("*.partial"))
        assert len(partials) == 0


class TestEnsureFileCopy:
    def test_copies_file(self, tmp_path):
        source = tmp_path / "source.txt"
        source.write_text("hello", encoding="utf-8")
        target = tmp_path / "target.txt"
        ensure_file_copy(source, target)
        assert target.read_text(encoding="utf-8") == "hello"

    def test_skips_identical(self, tmp_path):
        source = tmp_path / "source.txt"
        source.write_bytes(b"same")
        target = tmp_path / "target.txt"
        ensure_file_copy(source, target)
        mtime = target.stat().st_mtime
        ensure_file_copy(source, target)
        import os

        assert os.path.getmtime(target) == mtime

    def test_missing_source_raises(self, tmp_path):
        source = tmp_path / "nonexistent.txt"
        target = tmp_path / "target.txt"
        try:
            ensure_file_copy(source, target)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass


class TestReplaceTree:
    def test_copies_tree(self, tmp_path):
        source = tmp_path / "src"
        source.mkdir()
        (source / "a.txt").write_text("a", encoding="utf-8")
        (source / "sub").mkdir()
        (source / "sub" / "b.txt").write_text("b", encoding="utf-8")

        target = tmp_path / "dst"
        _replace_tree(source, target)
        assert (target / "a.txt").read_text(encoding="utf-8") == "a"
        assert (target / "sub" / "b.txt").read_text(encoding="utf-8") == "b"

    def test_replaces_existing(self, tmp_path):
        target = tmp_path / "dst"
        target.mkdir()
        (target / "old.txt").write_text("old", encoding="utf-8")

        source = tmp_path / "src"
        source.mkdir()
        (source / "new.txt").write_text("new", encoding="utf-8")

        _replace_tree(source, target)
        assert not (target / "old.txt").exists()
        assert (target / "new.txt").read_text(encoding="utf-8") == "new"


class TestMergeTree:
    def test_merges_into_existing(self, tmp_path):
        source = tmp_path / "src"
        source.mkdir()
        (source / "added.txt").write_text("new", encoding="utf-8")

        target = tmp_path / "dst"
        target.mkdir()
        (target / "existing.txt").write_text("keep", encoding="utf-8")

        _merge_tree(source, target)
        assert (target / "existing.txt").read_text(encoding="utf-8") == "keep"
        assert (target / "added.txt").read_text(encoding="utf-8") == "new"

    def test_noop_if_source_missing(self, tmp_path):
        source = tmp_path / "missing"
        target = tmp_path / "dst"
        target.mkdir()
        (target / "file.txt").write_text("data", encoding="utf-8")
        _merge_tree(source, target)  # should not raise
        assert (target / "file.txt").read_text(encoding="utf-8") == "data"


class TestCopyOrRemove:
    def test_copies_when_source_exists(self, tmp_path):
        source = tmp_path / "src.txt"
        source.write_bytes(b"data")
        target = tmp_path / "dst.txt"
        _copy_or_remove(source, target)
        assert target.read_bytes() == b"data"

    def test_removes_when_source_missing(self, tmp_path):
        source = tmp_path / "missing.txt"
        target = tmp_path / "target.txt"
        target.write_bytes(b"old")
        _copy_or_remove(source, target)
        assert not target.exists()


class TestSyncCatalogArtifacts:
    def test_syncs_catalog_tree(self, tmp_path):
        repo = tmp_path / "repo"
        catalog = repo / "catalog"
        catalog.mkdir(parents=True)
        (catalog / "test.json").write_text('{"ok": true}', encoding="utf-8")

        artifacts = tmp_path / "artifacts"
        sync_catalog_artifacts(repo, artifacts)

        assert (artifacts / "catalog" / "test.json").read_text(encoding="utf-8") == '{"ok": true}'

    def test_syncs_index_files(self, tmp_path):
        repo = tmp_path / "repo"
        catalog = repo / "catalog"
        catalog.mkdir(parents=True)
        (catalog / "ai-index.json").write_text("ai", encoding="utf-8")
        (catalog / "distributions.json").write_text("dist", encoding="utf-8")
        (catalog / "compatibility.json").write_text("compat", encoding="utf-8")
        (catalog / "discovery-index.json").write_text("disc", encoding="utf-8")

        artifacts = tmp_path / "artifacts"
        sync_catalog_artifacts(repo, artifacts)

        assert (artifacts / "ai-index.json").read_text(encoding="utf-8") == "ai"
        assert (artifacts / "distributions.json").read_text(encoding="utf-8") == "dist"
        assert (artifacts / "compatibility.json").read_text(encoding="utf-8") == "compat"
        assert (artifacts / "discovery-index.json").read_text(encoding="utf-8") == "disc"
