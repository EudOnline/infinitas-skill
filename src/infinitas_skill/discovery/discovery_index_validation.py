"""Validation helpers for the federated discovery index."""

from __future__ import annotations

from typing import Any


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_runtime_identity(runtime: dict[str, Any], prefix: str, errors: list[str]) -> None:
    if runtime.get("platform") != "openclaw":
        errors.append(f"{prefix}.runtime.platform must equal openclaw")
    for field in ("workspace_scope", "source_mode"):
        value = runtime.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}.runtime.{field} must be a non-empty string")
    for field in ("workspace_targets", "skill_precedence"):
        if not _string_list(runtime.get(field)):
            errors.append(f"{prefix}.runtime.{field} must be an array of strings")


def _validate_runtime_install_targets(
    runtime: dict[str, Any], prefix: str, errors: list[str]
) -> None:
    install_targets = runtime.get("install_targets")
    if not isinstance(install_targets, dict):
        errors.append(f"{prefix}.runtime.install_targets must be an object")
    else:
        for field in ("workspace", "shared"):
            if not _string_list(install_targets.get(field)):
                errors.append(
                    f"{prefix}.runtime.install_targets.{field} must be an array of strings"
                )


def _validate_runtime_requirements(runtime: dict[str, Any], prefix: str, errors: list[str]) -> None:
    requires = runtime.get("requires")
    if not isinstance(requires, dict):
        errors.append(f"{prefix}.runtime.requires must be an object")
    else:
        for field in ("tools", "bins", "env", "config"):
            if not _string_list(requires.get(field)):
                errors.append(f"{prefix}.runtime.requires.{field} must be an array of strings")


def _validate_runtime_capabilities(runtime: dict[str, Any], prefix: str, errors: list[str]) -> None:
    if not isinstance(runtime.get("plugin_capabilities"), dict):
        errors.append(f"{prefix}.runtime.plugin_capabilities must be an object")
    for field in ("background_tasks", "subagents"):
        if not isinstance(runtime.get(field), dict):
            errors.append(f"{prefix}.runtime.{field} must be an object")


def _validate_runtime_readiness(runtime: dict[str, Any], prefix: str, errors: list[str]) -> None:
    readiness = runtime.get("readiness")
    if not isinstance(readiness, dict):
        errors.append(f"{prefix}.runtime.readiness must be an object")
        return
    status = readiness.get("status")
    if not isinstance(status, str) or not status.strip():
        errors.append(f"{prefix}.runtime.readiness.status must be a non-empty string")
    for field in ("ready", "supports_background_tasks", "supports_plugins", "supports_subagents"):
        if not isinstance(readiness.get(field), bool):
            errors.append(f"{prefix}.runtime.readiness.{field} must be a boolean")


def _validate_runtime(runtime: dict[str, Any], prefix: str, errors: list[str]) -> None:
    _validate_runtime_identity(runtime, prefix, errors)
    _validate_runtime_install_targets(runtime, prefix, errors)
    _validate_runtime_requirements(runtime, prefix, errors)
    _validate_runtime_capabilities(runtime, prefix, errors)
    _validate_runtime_readiness(runtime, prefix, errors)


def _validate_skill_identity(skill: dict[str, Any], prefix: str, errors: list[str]) -> None:
    for field in (
        "name",
        "qualified_name",
        "source_registry",
        "default_install_version",
        "latest_version",
    ):
        value = skill.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}.{field} must be a non-empty string")
    if not isinstance(skill.get("summary"), str):
        errors.append(f"{prefix}.summary must be a string")
    if not isinstance(skill.get("source_priority"), int):
        errors.append(f"{prefix}.source_priority must be an integer")
    trust_level = skill.get("trust_level")
    if not isinstance(trust_level, str) or not trust_level.strip():
        errors.append(f"{prefix}.trust_level must be a non-empty string")
    if not isinstance(skill.get("install_requires_confirmation"), bool):
        errors.append(f"{prefix}.install_requires_confirmation must be a boolean")


def _validate_skill_lists(skill: dict[str, Any], prefix: str, errors: list[str]) -> None:
    for field in (
        "match_names",
        "available_versions",
        "use_when",
        "avoid_when",
        "runtime_assumptions",
        "tags",
        "attestation_formats",
        "capabilities",
    ):
        if not _string_list(skill.get(field)):
            errors.append(f"{prefix}.{field} must be an array of strings")
    if skill.get("workspace_targets") is not None and not _string_list(
        skill.get("workspace_targets")
    ):
        errors.append(f"{prefix}.workspace_targets must be an array of strings when present")


def _validate_skill_quality(skill: dict[str, Any], prefix: str, errors: list[str]) -> None:
    readiness = skill.get("runtime_readiness")
    if readiness is not None and (not isinstance(readiness, str) or not readiness.strip()):
        errors.append(f"{prefix}.runtime_readiness must be a non-empty string when present")
    maturity = skill.get("maturity")
    if not isinstance(maturity, str) or not maturity.strip():
        errors.append(f"{prefix}.maturity must be a non-empty string")
    if not isinstance(skill.get("quality_score"), int):
        errors.append(f"{prefix}.quality_score must be an integer")
    verified_at = skill.get("last_verified_at")
    if verified_at is not None and (not isinstance(verified_at, str) or not verified_at.strip()):
        errors.append(f"{prefix}.last_verified_at must be a non-empty string when present")
    trust_state = skill.get("trust_state")
    if not isinstance(trust_state, str) or not trust_state.strip():
        errors.append(f"{prefix}.trust_state must be a non-empty string")
    if not isinstance(skill.get("verified_support"), dict):
        errors.append(f"{prefix}.verified_support must be an object")


def _validate_skill(skill: object, index: int, errors: list[str]) -> None:
    prefix = f"discovery-index skills[{index}]"
    if not isinstance(skill, dict):
        errors.append(f"{prefix} must be an object")
        return
    _validate_skill_identity(skill, prefix, errors)
    _validate_skill_lists(skill, prefix, errors)
    _validate_skill_quality(skill, prefix, errors)
    runtime = skill.get("runtime")
    if runtime is not None:
        if not isinstance(runtime, dict):
            errors.append(f"{prefix}.runtime must be an object when present")
        else:
            _validate_runtime(runtime, prefix, errors)


def validate_discovery_index_payload(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["discovery-index payload must be an object"]
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("discovery-index schema_version must equal 1")
    for field in ("generated_at", "default_registry"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"discovery-index {field} must be a non-empty string")
    if not isinstance(payload.get("sources"), list):
        errors.append("discovery-index sources must be an array")
    policy = payload.get("resolution_policy")
    if not isinstance(policy, dict):
        errors.append("discovery-index resolution_policy must be an object")
    else:
        if policy.get("private_registry_first") is not True:
            errors.append("discovery-index resolution_policy.private_registry_first must be true")
        if policy.get("external_requires_confirmation") is not True:
            errors.append(
                "discovery-index resolution_policy.external_requires_confirmation must be true"
            )
        if policy.get("auto_install_mutable_sources") is not False:
            errors.append(
                "discovery-index resolution_policy.auto_install_mutable_sources must be false"
            )
    skills = payload.get("skills")
    if not isinstance(skills, list):
        errors.append("discovery-index skills must be an array")
        return errors
    for index, skill in enumerate(skills, start=1):
        _validate_skill(skill, index, errors)
    return errors
