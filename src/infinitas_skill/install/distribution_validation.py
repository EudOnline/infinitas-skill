"""Schema-level validation for signed distribution manifests."""

from __future__ import annotations

from typing import Any


def _require_string(mapping: object, key: str, label: str, errors: list[str]) -> object | None:
    value = mapping.get(key) if isinstance(mapping, dict) else None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
    return value


def _validate_skill(payload: dict[str, Any], errors: list[str]) -> None:
    skill = payload.get("skill")
    if not isinstance(skill, dict):
        errors.append("skill must be an object")
        return
    _require_string(skill, "name", "skill.name", errors)
    _require_string(skill, "version", "skill.version", errors)


def _validate_source_snapshot(payload: dict[str, Any], errors: list[str]) -> None:
    snapshot = payload.get("source_snapshot")
    if not isinstance(snapshot, dict):
        errors.append("source_snapshot must be an object")
        return
    for key in ("kind", "tag", "ref", "commit"):
        _require_string(snapshot, key, f"source_snapshot.{key}", errors)
    for key in ("immutable", "pushed"):
        if not isinstance(snapshot.get(key), bool):
            errors.append(f"source_snapshot.{key} must be boolean")


def _validate_bundle(payload: dict[str, Any], errors: list[str]) -> None:
    bundle = payload.get("bundle")
    if not isinstance(bundle, dict):
        errors.append("bundle must be an object")
        return
    _require_string(bundle, "path", "bundle.path", errors)
    if bundle.get("format") != "tar.gz":
        errors.append("bundle.format must be tar.gz")
    _require_string(bundle, "sha256", "bundle.sha256", errors)
    _require_string(bundle, "root_dir", "bundle.root_dir", errors)
    size = bundle.get("size")
    if not isinstance(size, int) or size < 0:
        errors.append("bundle.size must be a non-negative integer")
    file_count = bundle.get("file_count")
    if not isinstance(file_count, int) or file_count < 1:
        errors.append("bundle.file_count must be a positive integer")


def _validate_context(payload: dict[str, Any], key: str, errors: list[str]) -> None:
    context = payload.get(key)
    if not isinstance(context, dict):
        errors.append(f"{key} must be an object")
        return
    required_arrays = (
        ("registries_consulted", "resolved")
        if key == "registry"
        else ("steps", "registries_consulted")
    )
    for field in required_arrays:
        if not isinstance(context.get(field), list):
            errors.append(f"{key}.{field} must be an array")


def _validate_attestation_bundle(payload: dict[str, Any], errors: list[str]) -> None:
    attestation = payload.get("attestation_bundle")
    if not isinstance(attestation, dict):
        errors.append("attestation_bundle must be an object")
        return
    for key in (
        "provenance_path",
        "provenance_sha256",
        "signature_path",
        "signature_sha256",
        "namespace",
        "allowed_signers",
    ):
        _require_string(attestation, key, f"attestation_bundle.{key}", errors)
    formats = attestation.get("required_formats")
    if formats is not None and (not isinstance(formats, list) or not formats):
        errors.append("attestation_bundle.required_formats must be a non-empty array when present")
    elif isinstance(formats, list) and any(item not in {"ssh", "ci"} for item in formats):
        errors.append("attestation_bundle.required_formats entries must be ssh or ci")


def validate_distribution_manifest(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("kind") != "skill-distribution-manifest":
        errors.append("kind must be skill-distribution-manifest")
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    _validate_skill(payload, errors)
    _validate_source_snapshot(payload, errors)
    _validate_bundle(payload, errors)
    _validate_context(payload, "registry", errors)
    _validate_context(payload, "dependencies", errors)
    _validate_attestation_bundle(payload, errors)
    return errors
