"""OpenClaw-native skill contract loading."""

from __future__ import annotations

from pathlib import Path

from infinitas_skill.skills.canonical import CanonicalSkillError, load_skill_source

from .plugins import normalize_plugin_capabilities


class OpenClawSkillContractError(Exception):
    """Raised when an OpenClaw skill contract cannot be derived."""


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

    try:
        source = load_skill_source(path)
    except CanonicalSkillError as exc:  # pragma: no cover - passthrough guard
        raise OpenClawSkillContractError(str(exc)) from exc

    runtime = dict(source.get("openclaw_runtime") or {})
    verification = dict(source.get("verification") or {})
    runtime_verification = dict(source.get("runtime_verification") or {})
    plugin_capabilities = normalize_plugin_capabilities(runtime.get("plugin_capabilities"))
    license_value = runtime.get("license") or (source.get("distribution") or {}).get("license")
    source_mode = source.get("source_mode") or "unknown"

    runtime_payload = {
        "requires": _normalized_requires(source),
        "plugin_capabilities": plugin_capabilities,
    }
    if isinstance(runtime.get("workspace_scope"), str) and runtime.get("workspace_scope").strip():
        runtime_payload["workspace_scope"] = runtime["workspace_scope"].strip()
    if isinstance(license_value, str) and license_value.strip():
        runtime_payload["license"] = license_value.strip()

    verification_payload = {
        "required_runtimes": list(runtime_verification.get("required_runtimes") or []),
        "smoke_prompts": list(runtime_verification.get("smoke_prompts") or []),
        "legacy": {
            "required_platforms": list(
                runtime_verification.get("required_platforms_legacy")
                or verification.get("required_platforms")
                or []
            ),
            "required_platforms_deprecated": bool(
                verification.get("required_platforms_deprecated")
                if "required_platforms_deprecated" in verification
                else runtime_verification.get("required_platforms_deprecated")
            ),
        },
    }

    return {
        "platform": "openclaw",
        "source_mode": source_mode,
        "migration_only": source_mode == "legacy-migration",
        "runtime": runtime_payload,
        "verification": verification_payload,
        "source": source,
    }


__all__ = ["OpenClawSkillContractError", "load_openclaw_skill_contract"]
