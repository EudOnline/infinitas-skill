from __future__ import annotations

from src.infinitas_skill.openclaw.plugins import (
    _normalize_string_list,
    normalize_plugin_capabilities,
)


class TestNormalizeStringList:
    def test_valid_list(self):
        assert _normalize_string_list(["a", "b"]) == ["a", "b"]

    def test_skips_non_strings(self):
        assert _normalize_string_list(["a", 1, "b"]) == ["a", "b"]

    def test_skips_empty_strings(self):
        assert _normalize_string_list(["a", "", "b"]) == ["a", "b"]

    def test_whitespace_trimmed(self):
        assert _normalize_string_list(["  a  ", "b"]) == ["a", "b"]

    def test_none_input(self):
        assert _normalize_string_list(None) is None

    def test_empty_result(self):
        assert _normalize_string_list(["", ""]) is None


class TestNormalizePluginCapabilities:
    def test_valid_payload(self):
        payload = {"channels": ["a", "b"], "tools": ["x"]}
        result = normalize_plugin_capabilities(payload)
        assert result["channels"] == ["a", "b"]
        assert result["tools"] == ["x"]
        assert "web_search" not in result

    def test_non_dict(self):
        assert normalize_plugin_capabilities("bad") == {}

    def test_none(self):
        assert normalize_plugin_capabilities(None) == {}

    def test_unsupported_keys_ignored(self):
        payload = {"unsupported": ["a"], "channels": ["b"]}
        result = normalize_plugin_capabilities(payload)
        assert "unsupported" not in result
        assert result["channels"] == ["b"]
