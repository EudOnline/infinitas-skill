from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infinitas_skill.openclaw.contracts import (
    OpenClawContractError,
    _require_nonempty_string,
    _require_string_list,
    load_openclaw_runtime_profile,
)


class TestRequireNonemptyString:
    def test_valid(self):
        assert _require_nonempty_string("hello", field="test") == "hello"

    def test_whitespace_trimmed(self):
        assert _require_nonempty_string("  hello  ", field="test") == "hello"

    def test_empty_raises(self):
        with pytest.raises(OpenClawContractError) as exc:
            _require_nonempty_string("", field="test")
        assert "must be a non-empty string" in str(exc.value)

    def test_none_raises(self):
        with pytest.raises(OpenClawContractError) as exc:
            _require_nonempty_string(None, field="test")
        assert "must be a non-empty string" in str(exc.value)


class TestRequireStringList:
    def test_valid(self):
        assert _require_string_list(["a", "b"], field="test") == ["a", "b"]

    def test_empty_raises(self):
        with pytest.raises(OpenClawContractError) as exc:
            _require_string_list([], field="test")
        assert "must be a non-empty list" in str(exc.value)

    def test_non_string_raises(self):
        with pytest.raises(OpenClawContractError) as exc:
            _require_string_list([1, 2], field="test")
        assert "must contain only non-empty strings" in str(exc.value)


class TestLoadOpenclawRuntimeProfile:
    def test_valid_profile(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "profiles").mkdir()
            (root / "profiles" / "openclaw.json").write_text(
                json.dumps(
                    {
                        "platform": "openclaw",
                        "runtime": {
                            "skill_dir_candidates": [".claude/skills"],
                            "entrypoint": "SKILL.md",
                        },
                        "capabilities": {},
                        "contract": {
                            "sources": ["https://example.com"],
                            "last_verified": "2026-04-01",
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = load_openclaw_runtime_profile(root)
            assert result["platform"] == "openclaw"

    def test_missing_file_raises(self):
        with TemporaryDirectory() as td:
            with pytest.raises(OpenClawContractError) as exc:
                load_openclaw_runtime_profile(Path(td))
            assert "missing OpenClaw profile" in str(exc.value)

    def test_wrong_platform_raises(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "profiles").mkdir()
            (root / "profiles" / "openclaw.json").write_text(
                json.dumps(
                    {
                        "platform": "codex",
                        "runtime": {"skill_dir_candidates": ["."], "entrypoint": "SKILL.md"},
                        "capabilities": {},
                        "contract": {
                            "sources": ["https://example.com"],
                            "last_verified": "2026-04-01",
                        },
                    }
                ),
                encoding="utf-8",
            )
            with pytest.raises(OpenClawContractError) as exc:
                load_openclaw_runtime_profile(root)
            assert "wrong platform" in str(exc.value)

    def test_invalid_runtime_raises(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "profiles").mkdir()
            (root / "profiles" / "openclaw.json").write_text(
                json.dumps(
                    {
                        "platform": "openclaw",
                        "runtime": "bad",
                        "capabilities": {},
                        "contract": {
                            "sources": ["https://example.com"],
                            "last_verified": "2026-04-01",
                        },
                    }
                ),
                encoding="utf-8",
            )
            with pytest.raises(OpenClawContractError) as exc:
                load_openclaw_runtime_profile(root)
            assert "runtime must be an object" in str(exc.value)
