from __future__ import annotations

from .ai_index_builder import _relative_repo_path

OPENCLAW_RUNTIME_TARGETS = [
    "skills",
    ".agents/skills",
    "~/.agents/skills",
    "~/.openclaw/skills",
]


def validate_ai_index_payload(payload: dict) -> list:
    errors = []
    if not isinstance(payload, dict):
        return ["ai-index payload must be an object"]

    if payload.get("schema_version") != 1:
        errors.append("ai-index schema_version must equal 1")
    if (
        not isinstance(payload.get("generated_at"), str)
        or not payload.get("generated_at", "").strip()
    ):
        errors.append("ai-index generated_at must be a non-empty string")

    registry = payload.get("registry")
    if not isinstance(registry, dict):
        errors.append("ai-index registry must be an object")

    install_policy = payload.get("install_policy")
    if not isinstance(install_policy, dict):
        errors.append("ai-index install_policy must be an object")
    else:
        if install_policy.get("mode") != "immutable-only":
            errors.append("ai-index install_policy.mode must be immutable-only")
        if install_policy.get("direct_source_install_allowed") is not False:
            errors.append("ai-index direct_source_install_allowed must be false")
        if install_policy.get("require_attestation") is not True:
            errors.append("ai-index require_attestation must be true")
        if install_policy.get("require_sha256") is not True:
            errors.append("ai-index require_sha256 must be true")

    skills = payload.get("skills")
    if not isinstance(skills, list):
        errors.append("ai-index skills must be an array")
        return errors

    for index, skill in enumerate(skills, start=1):
        prefix = f"ai-index skills[{index}]"
        if not isinstance(skill, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in [
            "name",
            "qualified_name",
            "summary",
            "default_install_version",
            "latest_version",
        ]:
            if not isinstance(skill.get(field), str) or not skill.get(field, "").strip():
                errors.append(f"{prefix}.{field} must be a non-empty string")
        for field in [
            "use_when",
            "avoid_when",
            "runtime_assumptions",
            "available_versions",
            "tags",
            "capabilities",
        ]:
            value = skill.get(field)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"{prefix}.{field} must be an array of strings")
        if not isinstance(skill.get("maturity"), str) or not skill.get("maturity", "").strip():
            errors.append(f"{prefix}.maturity must be a non-empty string")
        if not isinstance(skill.get("quality_score"), int):
            errors.append(f"{prefix}.quality_score must be an integer")
        last_verified_at = skill.get("last_verified_at")
        if last_verified_at is not None and (
            not isinstance(last_verified_at, str) or not last_verified_at.strip()
        ):
            errors.append(f"{prefix}.last_verified_at must be a non-empty string when present")
        if (
            not isinstance(skill.get("trust_state"), str)
            or not skill.get("trust_state", "").strip()
        ):
            errors.append(f"{prefix}.trust_state must be a non-empty string")
        if not isinstance(skill.get("verified_support"), dict):
            errors.append(f"{prefix}.verified_support must be an object")

        for platform, support_payload in (skill.get("verified_support") or {}).items():
            platform_prefix = f"{prefix}.verified_support.{platform}"
            if not isinstance(platform, str) or not platform.strip():
                errors.append(f"{prefix}.verified_support keys must be non-empty strings")
                continue
            if not isinstance(support_payload, dict):
                errors.append(f"{platform_prefix} must be an object")
                continue
            state = support_payload.get("state")
            if not isinstance(state, str) or not state.strip():
                errors.append(f"{platform_prefix}.state must be a non-empty string")
            for field in ["checked_at", "checker", "evidence_path", "note"]:
                value = support_payload.get(field)
                if value is not None and (not isinstance(value, str) or not value.strip()):
                    errors.append(
                        f"{platform_prefix}.{field} must be a non-empty string when present"
                    )

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
        else:
            for field in ["tools", "env"]:
                value = requires.get(field)
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    errors.append(f"{prefix}.requires.{field} must be an array of strings")

        runtime = skill.get("runtime")
        if not isinstance(runtime, dict):
            errors.append(f"{prefix}.runtime must be an object")
        else:
            if runtime.get("platform") != "openclaw":
                errors.append(f"{prefix}.runtime.platform must equal openclaw")
            source_mode = runtime.get("source_mode")
            if not isinstance(source_mode, str) or not source_mode.strip():
                errors.append(f"{prefix}.runtime.source_mode must be a non-empty string")
            workspace_scope = runtime.get("workspace_scope")
            if workspace_scope not in {"workspace", "user"}:
                errors.append(f"{prefix}.runtime.workspace_scope must be workspace or user")
            workspace_targets = runtime.get("workspace_targets")
            if workspace_targets != OPENCLAW_RUNTIME_TARGETS:
                errors.append(
                    f"{prefix}.runtime.workspace_targets must equal the documented OpenClaw targets"
                )
            skill_precedence = runtime.get("skill_precedence")
            if not isinstance(skill_precedence, list) or not all(
                isinstance(item, str) for item in skill_precedence
            ):
                errors.append(f"{prefix}.runtime.skill_precedence must be an array of strings")
            install_targets = runtime.get("install_targets")
            if not isinstance(install_targets, dict):
                errors.append(f"{prefix}.runtime.install_targets must be an object")
            else:
                for field in ["workspace", "shared"]:
                    value = install_targets.get(field)
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        errors.append(
                            f"{prefix}.runtime.install_targets.{field} must be an array of strings"
                        )
            requires = runtime.get("requires")
            if not isinstance(requires, dict):
                errors.append(f"{prefix}.runtime.requires must be an object")
            else:
                for field in ["tools", "bins", "env", "config"]:
                    value = requires.get(field)
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        errors.append(
                            f"{prefix}.runtime.requires.{field} must be an array of strings"
                        )
            plugin_capabilities = runtime.get("plugin_capabilities")
            if not isinstance(plugin_capabilities, dict):
                errors.append(f"{prefix}.runtime.plugin_capabilities must be an object")
            for field in ["background_tasks", "subagents", "legacy_compatibility"]:
                if not isinstance(runtime.get(field), dict):
                    errors.append(f"{prefix}.runtime.{field} must be an object")
            readiness = runtime.get("readiness")
            if not isinstance(readiness, dict):
                errors.append(f"{prefix}.runtime.readiness must be an object")
            else:
                status = readiness.get("status")
                if not isinstance(status, str) or not status.strip():
                    errors.append(f"{prefix}.runtime.readiness.status must be a non-empty string")
                for field in [
                    "ready",
                    "supports_background_tasks",
                    "supports_plugins",
                    "supports_subagents",
                ]:
                    if not isinstance(readiness.get(field), bool):
                        errors.append(f"{prefix}.runtime.readiness.{field} must be a boolean")

        available_versions = (
            skill.get("available_versions")
            if isinstance(skill.get("available_versions"), list)
            else []
        )
        versions = skill.get("versions")
        if not isinstance(versions, dict):
            errors.append(f"{prefix}.versions must be an object")
            continue
        default_version = skill.get("default_install_version")
        latest_version = skill.get("latest_version")
        if default_version not in available_versions:
            errors.append(f"{prefix}.default_install_version must exist in available_versions")
        if latest_version not in available_versions:
            errors.append(f"{prefix}.latest_version must exist in available_versions")
        for version in available_versions:
            if version not in versions:
                errors.append(
                    f"{prefix}.available_versions contains {version!r} missing from versions"
                )
        for version, version_payload in versions.items():
            version_prefix = f"{prefix}.versions.{version}"
            if not isinstance(version_payload, dict):
                errors.append(f"{version_prefix} must be an object")
                continue
            if version_payload.get("installable") is True:
                for field in [
                    "manifest_path",
                    "bundle_path",
                    "bundle_sha256",
                    "attestation_path",
                    "published_at",
                ]:
                    value = version_payload.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f"{version_prefix}.{field} must be a non-empty string")
                if (
                    not isinstance(version_payload.get("distribution_manifest_path"), str)
                    or not version_payload.get("distribution_manifest_path", "").strip()
                ):
                    errors.append(
                        f"{version_prefix}.distribution_manifest_path must be a non-empty string"
                    )
                for field in ["manifest_path", "bundle_path", "attestation_path"]:
                    value = version_payload.get(field)
                    if isinstance(value, str) and value.strip() and not _relative_repo_path(value):
                        errors.append(f"{version_prefix}.{field} must be repo-relative")
                distribution_manifest_path = version_payload.get("distribution_manifest_path")
                if (
                    isinstance(distribution_manifest_path, str)
                    and distribution_manifest_path.strip()
                    and not _relative_repo_path(distribution_manifest_path)
                ):
                    errors.append(
                        f"{version_prefix}.distribution_manifest_path must be repo-relative"
                    )
                signature_path = version_payload.get("attestation_signature_path")
                if signature_path is not None and (
                    not isinstance(signature_path, str)
                    or not signature_path.strip()
                    or not _relative_repo_path(signature_path)
                ):
                    errors.append(
                        f"{version_prefix}.attestation_signature_path must be "
                        "repo-relative when present"
                    )
                if (
                    not isinstance(version_payload.get("trust_state"), str)
                    or not version_payload.get("trust_state", "").strip()
                ):
                    errors.append(f"{version_prefix}.trust_state must be a non-empty string")
                attestation_formats = version_payload.get("attestation_formats")
                if not isinstance(attestation_formats, list) or not all(
                    isinstance(item, str) for item in attestation_formats
                ):
                    errors.append(
                        f"{version_prefix}.attestation_formats must be an array of strings"
                    )
                stability = version_payload.get("stability")
                if not isinstance(stability, str) or not stability.strip():
                    errors.append(f"{version_prefix}.stability must be a non-empty string")
                resolution = version_payload.get("resolution")
                if not isinstance(resolution, dict):
                    errors.append(f"{version_prefix}.resolution must be an object")
                else:
                    preferred_source = resolution.get("preferred_source")
                    if not isinstance(preferred_source, str) or not preferred_source.strip():
                        errors.append(
                            f"{version_prefix}.resolution.preferred_source "
                            "must be a non-empty string"
                        )
                    if resolution.get("fallback_allowed") is not False:
                        errors.append(f"{version_prefix}.resolution.fallback_allowed must be false")

    return errors


__all__ = ["validate_ai_index_payload"]
