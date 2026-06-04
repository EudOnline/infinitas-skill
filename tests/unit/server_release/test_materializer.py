"""Characterization tests for server.modules.release.materializer pure functions.

These tests cover the side-effect-free helper functions that can be tested
in isolation without database, filesystem, or subprocess dependencies.

Note: Importing server.modules.release.materializer triggers the
server.models ↔ server.modules.release.models circular re-export chain.
We import server.models first to establish the Base class before the
release models try to inherit from it.
"""
from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path

# Bootstrap the model layer to break the circular import:
# server.models must be loaded before server.modules.release.models
import server.models  # noqa: F401

from server.modules.release.bundle import (
    artifact_object_path,
    bundle_bytes,
    canonical_json_bytes,
    content_ref_commit,
)


class TestCanonicalJsonBytes:
    def test_basic(self):
        payload = {"z": 1, "a": 2}
        result = canonical_json_bytes(payload)
        text = result.decode("utf-8")
        # sorted keys
        assert text.index('"a"') < text.index('"z"')
        # trailing newline
        assert text.endswith("\n")
        parsed = json.loads(text)
        assert parsed == {"z": 1, "a": 2}

    def test_unicode(self):
        payload = {"name": "中文测试"}
        result = canonical_json_bytes(payload)
        text = result.decode("utf-8")
        assert "中文测试" in text

    def test_empty_dict(self):
        result = canonical_json_bytes({})
        assert json.loads(result) == {}


class TestContentRefCommit:
    def test_with_hash(self):
        assert content_ref_commit("https://example.com/repo#abc123", "fallback") == "abc123"

    def test_no_hash(self):
        assert content_ref_commit("https://example.com/repo", "fallback") == "fallback"

    def test_empty(self):
        assert content_ref_commit("", "fallback") == "fallback"

    def test_hash_with_whitespace(self):
        assert content_ref_commit("ref#  def ", "fb") == "def"


class TestBundleBytes:
    def test_creates_valid_tar_gz(self):
        data, count = bundle_bytes(
            skill_slug="test-skill",
            content_ref="https://example.com#abc123",
            metadata={"version": "1.0.0"},
        )
        assert count == 2
        assert len(data) > 0

        # Verify it's a valid gzip'd tar
        buffer = io.BytesIO(data)
        with gzip.GzipFile(fileobj=buffer, mode="rb") as gz:
            with tarfile.open(fileobj=gz, mode="r") as archive:
                names = [m.name for m in archive.getmembers()]
        assert "test-skill/snapshot/content-ref.txt" in names
        assert "test-skill/snapshot/metadata.json" in names

    def test_content_ref_in_bundle(self):
        data, _ = bundle_bytes(
            skill_slug="myskill",
            content_ref="commit-hash-123",
            metadata={},
        )
        buffer = io.BytesIO(data)
        with gzip.GzipFile(fileobj=buffer, mode="rb") as gz:
            with tarfile.open(fileobj=gz, mode="r") as archive:
                content_file = archive.extractfile("myskill/snapshot/content-ref.txt")
                assert content_file is not None
                content = content_file.read().decode("utf-8")
        assert "commit-hash-123" in content

    def test_metadata_in_bundle(self):
        metadata = {"version": "2.0.0", "name": "test"}
        data, _ = bundle_bytes(
            skill_slug="skill",
            content_ref="ref",
            metadata=metadata,
        )
        buffer = io.BytesIO(data)
        with gzip.GzipFile(fileobj=buffer, mode="rb") as gz:
            with tarfile.open(fileobj=gz, mode="r") as archive:
                meta_file = archive.extractfile("skill/snapshot/metadata.json")
                assert meta_file is not None
                parsed = json.loads(meta_file.read().decode("utf-8"))
        assert parsed["version"] == "2.0.0"


class TestArtifactObjectPath:
    def test_valid_path(self, tmp_path):
        root = tmp_path / "artifacts"
        root.mkdir()
        result = artifact_object_path(artifact_root=root, storage_uri="objects/sha256/abc123")
        assert result == (root / "objects" / "sha256" / "abc123").resolve()

    def test_path_traversal_rejected(self, tmp_path):
        root = tmp_path / "artifacts"
        root.mkdir()
        try:
            artifact_object_path(artifact_root=root, storage_uri="../../etc/passwd")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as exc:
            assert "escapes" in str(exc)

    def test_empty_storage_uri(self, tmp_path):
        root = tmp_path / "artifacts"
        root.mkdir()
        result = artifact_object_path(artifact_root=root, storage_uri="")
        assert result == root.resolve()
