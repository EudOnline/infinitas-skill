from __future__ import annotations

from infinitas_skill.discovery.ai_index_validation import validate_ai_index_payload


def test_validate_ai_index_payload_reports_core_contract_failures() -> None:
    errors = validate_ai_index_payload(
        {
            "schema_version": 0,
            "generated_at": "",
            "registry": {},
            "install_policy": {"mode": "mutable"},
            "skills": [
                {
                    "name": "",
                    "qualified_name": "",
                    "summary": "",
                    "default_install_version": "1.0.0",
                    "latest_version": "1.0.0",
                }
            ],
        }
    )

    assert "ai-index schema_version must equal 1" in errors
    assert "ai-index generated_at must be a non-empty string" in errors
    assert "ai-index install_policy.mode must be immutable-only" in errors
    assert "ai-index skills[1].name must be a non-empty string" in errors


def test_quality_score_may_be_unscored() -> None:
    from infinitas_skill.discovery.ai_index_payload_validation import _validate_skill

    errors: list[str] = []
    _validate_skill(
        {
            "name": "demo",
            "qualified_name": "owner/demo",
            "summary": "Demo",
            "default_install_version": "1.0.0",
            "latest_version": "1.0.0",
            "available_versions": [],
            "use_when": [],
            "avoid_when": [],
            "runtime_assumptions": [],
            "tags": [],
            "capabilities": [],
            "maturity": "unspecified",
            "quality_score": None,
            "last_verified_at": None,
            "trust_state": "private-first",
            "verified_support": {},
            "entrypoints": {"skill_md": "SKILL.md"},
            "requires": {"tools": [], "env": []},
            "runtime": {},
            "versions": {},
        },
        1,
        errors,
    )

    assert not any("quality_score" in error for error in errors)
