"""Characterization tests for server.modules.release.materializer pure functions.

These tests cover the side-effect-free helper functions that can be tested
in isolation without database, filesystem, or subprocess dependencies.

The release bundle helpers import directly from their owning modules and do not
need a central model facade bootstrap.
"""

from __future__ import annotations

import json

from server.modules.release.bundle import (
    artifact_object_path,
    canonical_json_bytes,
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
