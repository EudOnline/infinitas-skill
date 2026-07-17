"""Canonical skill source loading."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .schema_version import validate_schema_version

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CanonicalSkillError(Exception):
    def __init__(self, errors: str | Sequence[str]) -> None:
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


REQUIRED_CANONICAL_FIELDS = [
    "schema_version",
    "name",
    "summary",
    "description",
    "instructions_body",
    "tool_intents",
    "verification",
]


def is_canonical_skill_dir(path: Path) -> bool:
    return path.is_dir() and (path / "skill.json").is_file()


def _normalized_verification_payload(verification: dict) -> dict:
    verification = dict(verification or {}) if isinstance(verification, dict) else {}
    required_runtimes = verification.get("required_runtimes")
    smoke_prompts = verification.get("smoke_prompts")
    return {
        "required_runtimes": list(required_runtimes) if isinstance(required_runtimes, list) else [],
        "smoke_prompts": list(smoke_prompts) if isinstance(smoke_prompts, list) else [],
    }


def validate_canonical_payload(payload: dict) -> list[str]:
    errors = []
    _schema_version, schema_errors = validate_schema_version(payload)
    errors.extend(schema_errors)
    if not isinstance(payload, dict):
        return ["canonical skill payload must be an object"]
    for field in REQUIRED_CANONICAL_FIELDS:
        if field not in payload:
            errors.append(f"missing required canonical field {field}")
    name = payload.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append(f"invalid canonical name {name!r}")
    for key in ["summary", "description", "instructions_body"]:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be a non-empty string")
    errors.extend(_validate_tool_intents(payload.get("tool_intents")))
    errors.extend(_validate_verification(payload.get("verification")))
    for field in ["distribution", "degrades_to", "openclaw_runtime"]:
        value = payload.get(field)
        if value is not None and not isinstance(value, dict):
            errors.append(f"{field} must be an object when present")
    return errors


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_tool_intents(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["tool_intents must be an object"]
    return [
        f"tool_intents.{key} must be an array of strings"
        for key in ["required", "optional"]
        if not _string_list(value.get(key))
    ]


def _validate_verification(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["verification must be an object"]
    errors = []
    if "required_platforms" in value:
        errors.append("verification.required_platforms is not supported")
    if not _string_list(value.get("required_runtimes")):
        errors.append("verification.required_runtimes must be an array of strings")
    smoke_prompts = value.get("smoke_prompts")
    if smoke_prompts is not None and not _string_list(smoke_prompts):
        errors.append("verification.smoke_prompts must be an array of strings when present")
    return errors


def _load_platform_overrides(skill_dir: Path) -> dict:
    overlays: dict[str, Any] = {}
    platforms_dir = skill_dir / "platforms"
    if not platforms_dir.is_dir():
        return overlays
    for path in sorted(platforms_dir.glob("*.json")):
        try:
            overlays[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise CanonicalSkillError(f"invalid JSON in {path}: {exc}") from exc
    return overlays


def load_canonical_skill(path: Path) -> dict:
    skill_dir = Path(path).resolve()
    payload_path = skill_dir / "skill.json"
    if not payload_path.is_file():
        raise CanonicalSkillError(f"missing skill.json in canonical skill directory: {skill_dir}")
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CanonicalSkillError(f"invalid JSON in {payload_path}: {exc}") from exc
    errors = validate_canonical_payload(payload)
    instructions_body_path = skill_dir / payload.get("instructions_body", "")
    if not instructions_body_path.is_file():
        errors.append(f"missing canonical instructions body: {payload.get('instructions_body')!r}")
    if errors:
        raise CanonicalSkillError(errors)
    return {
        "schema_version": payload["schema_version"],
        "name": payload.get("name"),
        "summary": payload.get("summary"),
        "description": payload.get("description"),
        "triggers": list(payload.get("triggers") or []),
        "examples": list(payload.get("examples") or []),
        "instructions_body_path": str(instructions_body_path),
        "tool_intents": {
            "required": list((payload.get("tool_intents") or {}).get("required") or []),
            "optional": list((payload.get("tool_intents") or {}).get("optional") or []),
        },
        "platform_overrides": _load_platform_overrides(skill_dir),
        "distribution": dict(payload.get("distribution") or {}),
        "verification": _normalized_verification_payload(payload.get("verification") or {}),
        "degrades_to": dict(payload.get("degrades_to") or {}),
        "openclaw_runtime": dict(payload.get("openclaw_runtime") or {}),
        "source_mode": "canonical",
        "source_dir": str(skill_dir),
        "payload_path": str(payload_path),
    }


def load_skill_source(path: Path) -> dict:
    candidate = Path(path).resolve()
    if is_canonical_skill_dir(candidate):
        return load_canonical_skill(candidate)
    raise CanonicalSkillError(f"unsupported skill source layout: {candidate}")


__all__ = [
    "CanonicalSkillError",
    "REQUIRED_CANONICAL_FIELDS",
    "is_canonical_skill_dir",
    "validate_canonical_payload",
    "load_canonical_skill",
    "load_skill_source",
]
