from __future__ import annotations

from .ai_index_builder import OPENCLAW_INTEROP, _relative_repo_path


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
            "agent_compatible",
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

        compatibility = skill.get("compatibility")
        if compatibility is not None:
            if not isinstance(compatibility, dict):
                errors.append(f"{prefix}.compatibility must be an object when present")
            else:
                declared_support = compatibility.get("declared_support")
                if not isinstance(declared_support, list) or not all(
                    isinstance(item, str) for item in declared_support
                ):
                    errors.append(
                        f"{prefix}.compatibility.declared_support must be an array of strings"
                    )
                verified_support = compatibility.get("verified_support")
                if not isinstance(verified_support, dict):
                    errors.append(f"{prefix}.compatibility.verified_support must be an object")
                else:
                    for platform, support_payload in verified_support.items():
                        platform_prefix = f"{prefix}.compatibility.verified_support.{platform}"
                        if not isinstance(platform, str) or not platform.strip():
                            errors.append(
                                f"{prefix}.compatibility.verified_support "
                                "keys must be non-empty strings"
                            )
                            continue
                        if not isinstance(support_payload, dict):
                            errors.append(f"{platform_prefix} must be an object")
                            continue
                        state = support_payload.get("state")
                        if not isinstance(state, str) or not state.strip():
                            errors.append(f"{platform_prefix}.state must be a non-empty string")
                        for field in ["checked_at", "checker", "evidence_path", "note"]:
                            value = support_payload.get(field)
                            if value is not None and (
                                not isinstance(value, str) or not value.strip()
                            ):
                                errors.append(
                                    f"{platform_prefix}.{field} must be a "
                                    "non-empty string when present"
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

        interop = skill.get("interop")
        if not isinstance(interop, dict):
            errors.append(f"{prefix}.interop must be an object")
        else:
            openclaw = interop.get("openclaw")
            if not isinstance(openclaw, dict):
                errors.append(f"{prefix}.interop.openclaw must be an object")
            else:
                runtime_targets = openclaw.get("runtime_targets")
                if runtime_targets != OPENCLAW_INTEROP["runtime_targets"]:
                    errors.append(
                        f"{prefix}.interop.openclaw.runtime_targets must equal "
                        "the documented OpenClaw targets"
                    )
                if openclaw.get("import_supported") is not True:
                    errors.append(f"{prefix}.interop.openclaw.import_supported must be true")
                if openclaw.get("export_supported") is not True:
                    errors.append(f"{prefix}.interop.openclaw.export_supported must be true")
                public_publish = openclaw.get("public_publish")
                if not isinstance(public_publish, dict):
                    errors.append(f"{prefix}.interop.openclaw.public_publish must be an object")
                else:
                    clawhub = public_publish.get("clawhub")
                    if not isinstance(clawhub, dict):
                        errors.append(
                            f"{prefix}.interop.openclaw.public_publish.clawhub must be an object"
                        )
                    else:
                        if clawhub.get("supported") is not True:
                            errors.append(
                                f"{prefix}.interop.openclaw.public_publish."
                                "clawhub.supported must be true"
                            )
                        if clawhub.get("default") is not False:
                            errors.append(
                                f"{prefix}.interop.openclaw.public_publish."
                                "clawhub.default must be false"
                            )

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
                        errors.append(
                            f"{version_prefix}.resolution.fallback_allowed must be false"
                        )

    return errors


__all__ = ["validate_ai_index_payload"]
