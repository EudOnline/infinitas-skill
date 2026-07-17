from __future__ import annotations

import json
from pathlib import Path

import pytest

from infinitas_skill.skills.canonical import (
    CanonicalSkillError,
    is_canonical_skill_dir,
    load_canonical_skill,
    load_skill_source,
    validate_canonical_payload,
)


def _payload(**overrides: object) -> dict:
    payload = {
        "schema_version": 1,
        "name": "test-skill",
        "summary": "A test skill",
        "description": "Description",
        "instructions_body": "instructions.md",
        "tool_intents": {"required": ["read"], "optional": []},
        "verification": {"required_runtimes": ["python3.11"], "smoke_prompts": []},
    }
    payload.update(overrides)
    return payload


def test_validate_canonical_payload_accepts_current_schema() -> None:
    assert validate_canonical_payload(_payload()) == []


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"name": "Bad Name!"}, "invalid canonical name"),
        ({"summary": ""}, "summary must be a non-empty string"),
        ({"tool_intents": "bad"}, "tool_intents must be an object"),
        ({"verification": "bad"}, "verification must be an object"),
        (
            {"verification": {"required_platforms": ["codex"], "smoke_prompts": []}},
            "verification.required_platforms is not supported",
        ),
    ],
)
def test_validate_canonical_payload_rejects_invalid_data(overrides: dict, message: str) -> None:
    assert any(message in error for error in validate_canonical_payload(_payload(**overrides)))


def test_load_canonical_skill_returns_normalized_source(tmp_path: Path) -> None:
    (tmp_path / "skill.json").write_text(json.dumps(_payload()), encoding="utf-8")
    (tmp_path / "instructions.md").write_text("# Instructions\n", encoding="utf-8")

    result = load_canonical_skill(tmp_path)

    assert result["schema_version"] == 1
    assert result["source_mode"] == "canonical"
    assert result["verification"]["required_runtimes"] == ["python3.11"]
    assert "runtime_verification" not in result


def test_load_canonical_skill_requires_payload_and_instructions(tmp_path: Path) -> None:
    with pytest.raises(CanonicalSkillError, match="missing skill.json"):
        load_canonical_skill(tmp_path)

    (tmp_path / "skill.json").write_text(json.dumps(_payload()), encoding="utf-8")
    with pytest.raises(CanonicalSkillError, match="missing canonical instructions"):
        load_canonical_skill(tmp_path)


def test_load_skill_source_accepts_only_canonical_layout(tmp_path: Path) -> None:
    assert is_canonical_skill_dir(tmp_path) is False
    (tmp_path / "_meta.json").write_text("{}", encoding="utf-8")
    (tmp_path / "SKILL.md").write_text("# Old\n", encoding="utf-8")
    with pytest.raises(CanonicalSkillError, match="unsupported skill source layout"):
        load_skill_source(tmp_path)
