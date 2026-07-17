"""Validation helpers for the generated AI discovery index."""

from __future__ import annotations

from typing import Any

from .ai_index_builder import _relative_repo_path

OPENCLAW_RUNTIME_TARGETS = [
    "skills",
    ".agents/skills",
    "~/.agents/skills",
    "~/.openclaw/skills",
]


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_support(skill: dict[str, Any], prefix: str, errors: list[str]) -> None:
    support = skill.get("verified_support")
    if not isinstance(support, dict):
        errors.append(f"{prefix}.verified_support must be an object")
        return
    for platform, payload in support.items():
        platform_prefix = f"{prefix}.verified_support.{platform}"
        if not isinstance(platform, str) or not platform.strip():
            errors.append(f"{prefix}.verified_support keys must be non-empty strings")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{platform_prefix} must be an object")
            continue
        state = payload.get("state")
        if not isinstance(state, str) or not state.strip():
            errors.append(f"{platform_prefix}.state must be a non-empty string")
        for field in ("checked_at", "checker", "evidence_path", "note"):
            value = payload.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                errors.append(f"{platform_prefix}.{field} must be a non-empty string when present")


def _validate_entrypoints_and_requires(
    skill: dict[str, Any], prefix: str, errors: list[str]
) -> None:
    entrypoints = skill.get("entrypoints")
    if not isinstance(entrypoints, dict):
        errors.append(f"{prefix}.entrypoints must be an object")
    else:
        skill_md = entrypoints.get("skill_md")
        if not isinstance(skill_md, str) or not skill_md.strip():
            errors.append(f"{prefix}.entrypoints.skill_md must be a non-empty string")
        elif not _relative_repo_path(skill_md):
            errors.append(f"{prefix}.entrypoints.skill_md must be repo-relative")
    requires = skill.get("requires")
    if not isinstance(requires, dict):
        errors.append(f"{prefix}.requires must be an object")
        return
    for field in ("tools", "env"):
        if not _string_list(requires.get(field)):
            errors.append(f"{prefix}.requires.{field} must be an array of strings")


def _validate_runtime_lists(runtime: dict[str, Any], prefix: str, errors: list[str]) -> None:
    precedence = runtime.get("skill_precedence")
    if not _string_list(precedence):
        errors.append(f"{prefix}.runtime.skill_precedence must be an array of strings")
    install_targets = runtime.get("install_targets")
    if not isinstance(install_targets, dict):
        errors.append(f"{prefix}.runtime.install_targets must be an object")
    else:
        for field in ("workspace", "shared"):
            if not _string_list(install_targets.get(field)):
                errors.append(
                    f"{prefix}.runtime.install_targets.{field} must be an array of strings"
                )
    requires = runtime.get("requires")
    if not isinstance(requires, dict):
        errors.append(f"{prefix}.runtime.requires must be an object")
    else:
        for field in ("tools", "bins", "env", "config"):
            if not _string_list(requires.get(field)):
                errors.append(f"{prefix}.runtime.requires.{field} must be an array of strings")


def _validate_runtime(skill: dict[str, Any], prefix: str, errors: list[str]) -> None:
    runtime = skill.get("runtime")
    if not isinstance(runtime, dict):
        errors.append(f"{prefix}.runtime must be an object")
        return
    if runtime.get("platform") != "openclaw":
        errors.append(f"{prefix}.runtime.platform must equal openclaw")
    source_mode = runtime.get("source_mode")
    if not isinstance(source_mode, str) or not source_mode.strip():
        errors.append(f"{prefix}.runtime.source_mode must be a non-empty string")
    if runtime.get("workspace_scope") not in {"workspace", "user"}:
        errors.append(f"{prefix}.runtime.workspace_scope must be workspace or user")
    if runtime.get("workspace_targets") != OPENCLAW_RUNTIME_TARGETS:
        errors.append(
            f"{prefix}.runtime.workspace_targets must equal the documented OpenClaw targets"
        )
    _validate_runtime_lists(runtime, prefix, errors)
    if not isinstance(runtime.get("plugin_capabilities"), dict):
        errors.append(f"{prefix}.runtime.plugin_capabilities must be an object")
    for field in ("background_tasks", "subagents"):
        if not isinstance(runtime.get(field), dict):
            errors.append(f"{prefix}.runtime.{field} must be an object")
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


def _validate_installable_version(payload: dict[str, Any], prefix: str, errors: list[str]) -> None:
    for field in (
        "manifest_path",
        "bundle_path",
        "bundle_sha256",
        "attestation_path",
        "published_at",
    ):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}.{field} must be a non-empty string")
    distribution_path = payload.get("distribution_manifest_path")
    if not isinstance(distribution_path, str) or not distribution_path.strip():
        errors.append(f"{prefix}.distribution_manifest_path must be a non-empty string")
    for field in ("manifest_path", "bundle_path", "attestation_path"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip() and not _relative_repo_path(value):
            errors.append(f"{prefix}.{field} must be repo-relative")
    if (
        isinstance(distribution_path, str)
        and distribution_path.strip()
        and not _relative_repo_path(distribution_path)
    ):
        errors.append(f"{prefix}.distribution_manifest_path must be repo-relative")
    signature_path = payload.get("attestation_signature_path")
    if signature_path is not None and (
        not isinstance(signature_path, str)
        or not signature_path.strip()
        or not _relative_repo_path(signature_path)
    ):
        errors.append(f"{prefix}.attestation_signature_path must be repo-relative when present")
    for field in ("trust_state", "stability"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}.{field} must be a non-empty string")
    if not _string_list(payload.get("attestation_formats")):
        errors.append(f"{prefix}.attestation_formats must be an array of strings")
    resolution = payload.get("resolution")
    if not isinstance(resolution, dict):
        errors.append(f"{prefix}.resolution must be an object")
    else:
        preferred = resolution.get("preferred_source")
        if not isinstance(preferred, str) or not preferred.strip():
            errors.append(f"{prefix}.resolution.preferred_source must be a non-empty string")
        if resolution.get("fallback_allowed") is not False:
            errors.append(f"{prefix}.resolution.fallback_allowed must be false")


def _validate_versions(skill: dict[str, Any], prefix: str, errors: list[str]) -> None:
    available = skill.get("available_versions")
    available = available if isinstance(available, list) else []
    versions = skill.get("versions")
    if not isinstance(versions, dict):
        errors.append(f"{prefix}.versions must be an object")
        return
    for field in ("default_install_version", "latest_version"):
        if skill.get(field) not in available:
            errors.append(f"{prefix}.{field} must exist in available_versions")
    for version in available:
        if version not in versions:
            errors.append(f"{prefix}.available_versions contains {version!r} missing from versions")
    for version, payload in versions.items():
        version_prefix = f"{prefix}.versions.{version}"
        if not isinstance(payload, dict):
            errors.append(f"{version_prefix} must be an object")
        elif payload.get("installable") is True:
            _validate_installable_version(payload, version_prefix, errors)


def _validate_skill(skill: object, index: int, errors: list[str]) -> None:
    prefix = f"ai-index skills[{index}]"
    if not isinstance(skill, dict):
        errors.append(f"{prefix} must be an object")
        return
    for field in ("name", "qualified_name", "summary", "default_install_version", "latest_version"):
        value = skill.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{prefix}.{field} must be a non-empty string")
    for field in (
        "use_when",
        "avoid_when",
        "runtime_assumptions",
        "available_versions",
        "tags",
        "capabilities",
    ):
        if not _string_list(skill.get(field)):
            errors.append(f"{prefix}.{field} must be an array of strings")
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
    _validate_support(skill, prefix, errors)
    _validate_entrypoints_and_requires(skill, prefix, errors)
    _validate_runtime(skill, prefix, errors)
    _validate_versions(skill, prefix, errors)


def validate_ai_index_payload(payload: dict[str, Any]) -> list[str]:
    if not isinstance(payload, dict):
        return ["ai-index payload must be an object"]
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("ai-index schema_version must equal 1")
    generated_at = payload.get("generated_at")
    if not isinstance(generated_at, str) or not generated_at.strip():
        errors.append("ai-index generated_at must be a non-empty string")
    if not isinstance(payload.get("registry"), dict):
        errors.append("ai-index registry must be an object")
    policy = payload.get("install_policy")
    if not isinstance(policy, dict):
        errors.append("ai-index install_policy must be an object")
    else:
        if policy.get("mode") != "immutable-only":
            errors.append("ai-index install_policy.mode must be immutable-only")
        if policy.get("direct_source_install_allowed") is not False:
            errors.append("ai-index direct_source_install_allowed must be false")
        if policy.get("require_attestation") is not True:
            errors.append("ai-index require_attestation must be true")
        if policy.get("require_sha256") is not True:
            errors.append("ai-index require_sha256 must be true")
    skills = payload.get("skills")
    if not isinstance(skills, list):
        errors.append("ai-index skills must be an array")
        return errors
    for index, skill in enumerate(skills, start=1):
        _validate_skill(skill, index, errors)
    return errors
