from __future__ import annotations

from src.infinitas_skill.release.formatting import format_release_state


class TestFormatReleaseState:
    def test_basic(self):
        state = {
            "skill": {
                "name": "test-skill",
                "version": "1.0.0",
                "qualified_name": "acme/test-skill",
            },
            "mode": "stable-release",
            "git": {
                "branch": "main",
                "upstream": "origin/main",
                "head_commit": "abc123",
                "expected_tag": "skill/test-skill/v1.0.0",
            },
            "release_ready": True,
            "warnings": [],
            "errors": [],
            "release": {"releaser_identity": "alice"},
        }
        result = format_release_state(state)
        assert "skill: test-skill" in result
        assert "version: 1.0.0" in result
        assert "mode: stable-release" in result
        assert "release_ready: yes" in result

    def test_no_qualified_name(self):
        state = {
            "skill": {"name": "test-skill", "version": "1.0.0", "qualified_name": None},
            "mode": "stable-release",
            "git": {"branch": None, "upstream": None, "head_commit": "abc123", "expected_tag": "t"},
            "release_ready": False,
            "warnings": ["warn1"],
            "errors": ["err1"],
            "release": {},
        }
        result = format_release_state(state)
        assert "qualified_name: -" in result
        assert "branch: -" in result
        assert "upstream: -" in result
        assert "release_ready: no" in result
        assert "warn1" in result
        assert "err1" in result
