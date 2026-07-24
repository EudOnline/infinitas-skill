"""OpenClaw-native skill contract loading."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from infinitas_skill.skills.canonical import CanonicalSkillError, load_skill_source

from .plugins import normalize_plugin_capabilities


class OpenClawSkillContractError(Exception):
    """Raised when an OpenClaw skill contract cannot be derived."""


_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", re.DOTALL)
_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _strip_scalar(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1].strip()
    return text


def _native_frontmatter(skill_md: Path) -> dict[str, str]:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        raise OpenClawSkillContractError(f"could not read {skill_md}: {exc}") from exc
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise OpenClawSkillContractError(f"missing YAML frontmatter in {skill_md}")
    fields: dict[str, str] = {}
    for raw_line in match.group(1).splitlines():
        if raw_line[:1].isspace() or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        fields[key.strip()] = _strip_scalar(value)
    name = fields.get("name", "")
    description = fields.get("description", "")
    if not _NAME_RE.fullmatch(name):
        raise OpenClawSkillContractError(f"invalid OpenClaw skill name {name!r}")
    if not description:
        raise OpenClawSkillContractError("OpenClaw SKILL.md must declare a description")
    return fields


def _native_metadata(skill_dir: Path) -> dict[str, Any]:
    path = skill_dir / "_meta.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OpenClawSkillContractError(f"invalid native metadata {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise OpenClawSkillContractError(f"native metadata must contain an object: {path}")
    return payload


def _native_requires(metadata: dict[str, Any]) -> list[str]:
    requires = metadata.get("requires")
    if not isinstance(requires, dict):
        return []
    result: list[str] = []
    for field, prefix in (("tools", "tool"), ("bins", "bin"), ("env", "env")):
        values = requires.get(field)
        if not isinstance(values, list):
            continue
        for value in values:
            token = str(value).strip() if isinstance(value, str) else ""
            normalized = f"{prefix}:{token}" if token else ""
            if normalized and normalized not in result:
                result.append(normalized)
    return result


def _load_native_skill_source(path: Path) -> dict[str, Any]:
    skill_dir = path.parent if path.is_file() and path.name == "SKILL.md" else path
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise OpenClawSkillContractError(f"missing SKILL.md in OpenClaw skill: {skill_dir}")
    frontmatter = _native_frontmatter(skill_md)
    metadata = _native_metadata(skill_dir)
    verification = metadata.get("verification")
    if not isinstance(verification, dict):
        verification = {}
    smoke_prompts = verification.get("smoke_prompts")
    required_runtimes = verification.get("required_runtimes")
    return {
        "schema_version": metadata.get("schema_version", 1),
        "name": frontmatter["name"],
        "summary": metadata.get("summary") or frontmatter["description"],
        "description": frontmatter["description"],
        "instructions_body_path": str(skill_md),
        "tool_intents": {"required": [], "optional": []},
        "verification": {
            "required_runtimes": (
                list(required_runtimes) if isinstance(required_runtimes, list) else ["openclaw"]
            ),
            "smoke_prompts": list(smoke_prompts) if isinstance(smoke_prompts, list) else [],
        },
        "distribution": dict(metadata.get("distribution") or {}),
        "openclaw_runtime": {"requires": _native_requires(metadata)},
        "source_mode": "openclaw-native",
        "source_dir": str(skill_dir.resolve()),
        "payload_path": str(skill_md.resolve()),
        "metadata": metadata,
    }


def _normalized_requires(source: dict) -> list[str]:
    runtime = source.get("openclaw_runtime")
    if isinstance(runtime, dict):
        requires = runtime.get("requires")
        if isinstance(requires, list):
            result = []
            for item in requires:
                if not isinstance(item, str):
                    continue
                token = item.strip()
                if token and token not in result:
                    result.append(token)
            if result:
                return result

    result = []
    for intent in (source.get("tool_intents") or {}).get("required") or []:
        if not isinstance(intent, str):
            continue
        token = intent.strip().replace("_", "-")
        if token and token not in result:
            result.append(token)
    return result


def load_openclaw_skill_contract(path: Path) -> dict:
    """Load the canonical OpenClaw runtime contract for one skill source."""

    candidate = Path(path).resolve()
    is_native_file = candidate.is_file() and candidate.name == "SKILL.md"
    is_native_directory = candidate.is_dir() and not (candidate / "skill.json").is_file()
    if is_native_file or (is_native_directory and (candidate / "SKILL.md").is_file()):
        source = _load_native_skill_source(candidate)
    else:
        try:
            source = load_skill_source(candidate)
        except CanonicalSkillError as exc:  # pragma: no cover - passthrough guard
            raise OpenClawSkillContractError(str(exc)) from exc

    runtime = dict(source.get("openclaw_runtime") or {})
    verification = dict(source.get("verification") or {})
    plugin_capabilities = normalize_plugin_capabilities(runtime.get("plugin_capabilities"))
    license_value = runtime.get("license") or (source.get("distribution") or {}).get("license")
    source_mode = source.get("source_mode") or "unknown"

    runtime_payload = {
        "requires": _normalized_requires(source),
        "plugin_capabilities": plugin_capabilities,
    }
    workspace_scope = runtime.get("workspace_scope")
    if isinstance(workspace_scope, str) and workspace_scope.strip():
        runtime_payload["workspace_scope"] = workspace_scope.strip()
    if isinstance(license_value, str) and license_value.strip():
        runtime_payload["license"] = license_value.strip()

    verification_payload = {
        "required_runtimes": list(verification.get("required_runtimes") or []),
        "smoke_prompts": list(verification.get("smoke_prompts") or []),
    }

    return {
        "platform": "openclaw",
        "source_mode": source_mode,
        "runtime": runtime_payload,
        "verification": verification_payload,
        "source": source,
    }


__all__ = ["OpenClawSkillContractError", "load_openclaw_skill_contract"]
