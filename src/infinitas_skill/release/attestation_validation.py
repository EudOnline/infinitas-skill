"""Schema-level validation for release attestation payloads."""

from __future__ import annotations

from typing import Any


def _require_string(mapping: object, key: str, label: str, errors: list[str]) -> object | None:
    value = mapping.get(key) if isinstance(mapping, dict) else None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
    return value


def _release_mode(payload: dict[str, Any], errors: list[str]) -> str:
    release = payload.get("release")
    if not isinstance(release, dict) or release.get("release_mode") is None:
        return "stable-release"
    mode = release.get("release_mode")
    if mode not in {"stable-release", "local-tag"}:
        errors.append("release.release_mode must be 'stable-release' or 'local-tag' when present")
        return "stable-release"
    return str(mode)


def _validate_skill(payload: dict[str, Any], errors: list[str]) -> None:
    skill = payload.get("skill")
    if not isinstance(skill, dict):
        errors.append("skill must be an object")
        return
    for key in ("name", "version", "path"):
        _require_string(skill, key, f"skill.{key}", errors)
    for key in ("owners", "maintainers"):
        if skill.get(key) is not None and not isinstance(skill.get(key), list):
            errors.append(f"skill.{key} must be an array when present")


def _validate_git(payload: dict[str, Any], errors: list[str]) -> None:
    git = payload.get("git")
    if not isinstance(git, dict):
        errors.append("git must be an object")
        return
    for key in ("commit", "expected_tag", "release_ref"):
        _require_string(git, key, f"git.{key}", errors)
    if git.get("signed_tag_verified") is not True:
        errors.append("git.signed_tag_verified must be true")


def _validate_snapshot(payload: dict[str, Any], release_mode: str, errors: list[str]) -> None:
    snapshot = payload.get("source_snapshot")
    if not isinstance(snapshot, dict):
        errors.append("source_snapshot must be an object")
        return
    for key in ("tag", "ref", "commit"):
        _require_string(snapshot, key, f"source_snapshot.{key}", errors)
    if snapshot.get("immutable") is not True:
        errors.append("source_snapshot.immutable must be true")
    pushed = snapshot.get("pushed")
    if not isinstance(pushed, bool):
        errors.append("source_snapshot.pushed must be boolean")
    elif release_mode == "stable-release" and pushed is not True:
        errors.append("source_snapshot.pushed must be true for stable-release attestations")
    elif release_mode == "local-tag" and pushed is not False:
        errors.append("source_snapshot.pushed must be false for local-tag attestations")


def _validate_context(payload: dict[str, Any], key: str, errors: list[str]) -> None:
    context = payload.get(key)
    if not isinstance(context, dict):
        errors.append(f"{key} must be an object")
        return
    arrays = (
        ("registries_consulted", "resolved")
        if key == "registry"
        else ("steps", "registries_consulted")
    )
    for field in arrays:
        if not isinstance(context.get(field), list):
            errors.append(f"{key}.{field} must be an array")


def _validate_review_and_release(payload: dict[str, Any], errors: list[str]) -> None:
    review = payload.get("review")
    if not isinstance(review, dict):
        errors.append("review must be an object")
    elif not isinstance(review.get("reviewers"), list):
        errors.append("review.reviewers must be an array")
    release = payload.get("release")
    if not isinstance(release, dict):
        errors.append("release must be an object")
        return
    identity = release.get("releaser_identity")
    if identity is not None and (not isinstance(identity, str) or not identity.strip()):
        errors.append("release.releaser_identity must be a non-empty string when present")
    for key in ("transfer_required", "transfer_authorized"):
        if not isinstance(release.get(key), bool):
            errors.append(f"release.{key} must be boolean")
    for key in (
        "authorized_signers",
        "authorized_releasers",
        "transfer_matches",
        "competing_claims",
    ):
        if not isinstance(release.get(key), list):
            errors.append(f"release.{key} must be an array")


def _validate_attestation(payload: dict[str, Any], errors: list[str]) -> None:
    attestation = payload.get("attestation")
    if not isinstance(attestation, dict):
        errors.append("attestation must be an object")
        return
    attestation_format = attestation.get("format")
    if attestation_format not in {"ssh", "ci"}:
        errors.append("attestation.format must be ssh or ci")
    if attestation.get("policy_mode") not in {"advisory", "enforce"}:
        errors.append("attestation.policy_mode must be advisory or enforce")
    for key in (
        "require_verified_attestation_for_release_output",
        "require_verified_attestation_for_distribution",
    ):
        if not isinstance(attestation.get(key), bool):
            errors.append(f"attestation.{key} must be boolean")
    required = (
        ("namespace", "allowed_signers", "signature_file", "signature_ext", "signer_identity")
        if attestation_format == "ssh"
        else ("generator",)
        if attestation_format == "ci"
        else ()
    )
    for key in required:
        _require_string(attestation, key, f"attestation.{key}", errors)


def _validate_ci(payload: dict[str, Any], errors: list[str]) -> None:
    attestation = payload.get("attestation")
    if not isinstance(attestation, dict) or attestation.get("format") != "ci":
        return
    ci = payload.get("ci")
    if not isinstance(ci, dict):
        errors.append("ci must be an object for CI attestations")
        return
    for key in ("provider", "repository", "workflow", "run_id", "run_attempt", "sha", "ref"):
        _require_string(ci, key, f"ci.{key}", errors)


def _validate_distribution(payload: dict[str, Any], errors: list[str]) -> None:
    distribution = payload.get("distribution")
    if distribution is None:
        return
    if not isinstance(distribution, dict):
        errors.append("distribution must be an object when present")
        return
    manifest_path = distribution.get("manifest_path")
    if manifest_path is not None and (
        not isinstance(manifest_path, str) or not manifest_path.strip()
    ):
        errors.append("distribution.manifest_path must be a non-empty string when present")
    bundle = distribution.get("bundle")
    if not isinstance(bundle, dict):
        errors.append("distribution.bundle must be an object")
        return
    for key in ("path", "sha256", "root_dir"):
        _require_string(bundle, key, f"distribution.bundle.{key}", errors)
    if bundle.get("format") != "tar.gz":
        errors.append("distribution.bundle.format must be tar.gz")
    size = bundle.get("size")
    if not isinstance(size, int) or size < 0:
        errors.append("distribution.bundle.size must be a non-negative integer")
    file_count = bundle.get("file_count")
    if not isinstance(file_count, int) or file_count < 1:
        errors.append("distribution.bundle.file_count must be a positive integer")


def validate_provenance_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    release_mode = _release_mode(payload, errors)
    if payload.get("kind") != "skill-release-attestation":
        errors.append("kind must be skill-release-attestation")
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    _validate_skill(payload, errors)
    _validate_git(payload, errors)
    _validate_snapshot(payload, release_mode, errors)
    _validate_context(payload, "registry", errors)
    _validate_context(payload, "dependencies", errors)
    _validate_review_and_release(payload, errors)
    _validate_attestation(payload, errors)
    _validate_ci(payload, errors)
    _validate_distribution(payload, errors)
    return errors
