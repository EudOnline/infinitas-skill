from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.infinitas_skill.compatibility.policy import (
    default_compatibility_policy,
    load_compatibility_policy,
    validate_compatibility_policy_payload,
)


class TestDefaultCompatibilityPolicy:
    def test_returns_deep_copy(self):
        p1 = default_compatibility_policy()
        p2 = default_compatibility_policy()
        assert p1 == p2
        assert p1 is not p2


class TestValidateCompatibilityPolicyPayload:
    def test_valid(self):
        assert validate_compatibility_policy_payload(default_compatibility_policy()) == []

    def test_non_dict(self):
        assert validate_compatibility_policy_payload("bad") == [
            "compatibility policy payload must be an object"
        ]

    def test_bad_platform_contracts(self):
        errors = validate_compatibility_policy_payload({"platform_contracts": "bad"})
        assert any("platform_contracts must be an object" in e for e in errors)

    def test_bad_max_age_days(self):
        errors = validate_compatibility_policy_payload(
            {"platform_contracts": {"max_age_days": 0, "stale_policy": "fail"}}
        )
        assert any("max_age_days must be an integer >= 1" in e for e in errors)

    def test_bad_stale_policy(self):
        errors = validate_compatibility_policy_payload(
            {"platform_contracts": {"max_age_days": 30, "stale_policy": "unknown"}}
        )
        assert any("stale_policy must be" in e for e in errors)

    def test_bad_verified_support(self):
        errors = validate_compatibility_policy_payload(
            {
                "platform_contracts": {"max_age_days": 30, "stale_policy": "fail"},
                "verified_support": "bad",
            }
        )
        assert any("verified_support must be an object" in e for e in errors)

    def test_bad_missing_policy(self):
        errors = validate_compatibility_policy_payload(
            {
                "platform_contracts": {"max_age_days": 30, "stale_policy": "fail"},
                "verified_support": {
                    "stale_after_days": 30,
                    "contract_newer_than_evidence_policy": "ignore",
                    "missing_policy": "bad",
                },
            }
        )
        assert any("missing_policy must be" in e for e in errors)


class TestLoadCompatibilityPolicy:
    def test_loads_from_file(self):
        with TemporaryDirectory() as td:
            config_dir = Path(td) / "config"
            config_dir.mkdir()
            (config_dir / "compatibility-policy.json").write_text(
                json.dumps(default_compatibility_policy()), encoding="utf-8"
            )
            result = load_compatibility_policy(td)
            assert result["platform_contracts"]["max_age_days"] == 30

    def test_missing_file_returns_default(self):
        with TemporaryDirectory() as td:
            result = load_compatibility_policy(td)
            assert result["platform_contracts"]["max_age_days"] == 30

    def test_invalid_file_raises(self):
        with TemporaryDirectory() as td:
            config_dir = Path(td) / "config"
            config_dir.mkdir()
            (config_dir / "compatibility-policy.json").write_text(
                json.dumps({"platform_contracts": "bad"}), encoding="utf-8"
            )
            with pytest.raises(ValueError) as exc:
                load_compatibility_policy(td)
            assert "platform_contracts must be an object" in str(exc.value)
