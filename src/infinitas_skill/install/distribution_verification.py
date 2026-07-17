"""Cryptographic and reproducibility verification for distribution manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infinitas_skill.hashing import sha256_file
from infinitas_skill.install.distribution_core import (
    DistributionError,
    inspect_distribution_bundle,
    load_json,
    normalize_build,
    normalize_file_manifest,
    resolve_manifest_ref,
)
from infinitas_skill.install.distribution_validation import validate_distribution_manifest
from infinitas_skill.release.attestation import (
    AttestationError,
    verify_attestation,
    verify_ci_attestation,
)
from infinitas_skill.release.state import ROOT


def _load_manifest(manifest_path: str | Path, root: Path) -> tuple[Path, dict[str, Any]]:
    manifest_ref = Path(manifest_path)
    if manifest_ref.is_absolute():
        resolved = manifest_ref.resolve()
    else:
        root_candidate = (root / manifest_ref).resolve()
        resolved = root_candidate if root_candidate.exists() else manifest_ref.resolve()
    try:
        payload = load_json(resolved)
    except Exception as exc:
        raise DistributionError(f"could not parse distribution manifest {resolved}: {exc}") from exc
    errors = validate_distribution_manifest(payload)
    if errors:
        raise DistributionError("; ".join(errors))
    return resolved, payload


def _resolve_artifacts(
    manifest_path: Path, payload: dict[str, Any], root: Path
) -> tuple[Path, Path, Path]:
    attestation = payload["attestation_bundle"]
    provenance_path = resolve_manifest_ref(manifest_path, attestation["provenance_path"], root=root)
    signature_path = resolve_manifest_ref(manifest_path, attestation["signature_path"], root=root)
    bundle_path = resolve_manifest_ref(manifest_path, payload["bundle"]["path"], root=root)
    for label, path in (
        ("attestation payload", provenance_path),
        ("attestation signature", signature_path),
        ("distribution bundle", bundle_path),
    ):
        if not path.exists():
            raise DistributionError(f"missing {label}: {path}")
    return provenance_path, signature_path, bundle_path


def _verify_artifact_metadata(
    payload: dict[str, Any], provenance_path: Path, signature_path: Path, bundle_path: Path
) -> None:
    attestation = payload["attestation_bundle"]
    expected_digests = (
        (provenance_path, attestation["provenance_sha256"], "attestation payload"),
        (signature_path, attestation["signature_sha256"], "attestation signature"),
        (bundle_path, payload["bundle"]["sha256"], "bundle"),
    )
    for path, expected, label in expected_digests:
        if sha256_file(path) != expected:
            raise DistributionError(f"{label} digest does not match manifest")
    if bundle_path.stat().st_size != payload["bundle"]["size"]:
        raise DistributionError("bundle size does not match manifest")


def _verify_attestation_formats(
    manifest_path: Path,
    payload: dict[str, Any],
    provenance_path: Path,
    root: Path,
    attestation_root: Path,
) -> dict[str, Any]:
    try:
        result = verify_attestation(provenance_path, root=attestation_root)
    except AttestationError as exc:
        raise DistributionError(str(exc)) from exc
    required = payload["attestation_bundle"].get("required_formats") or ["ssh"]
    verified = set(result.get("formats_verified") or [])
    if "ci" in required and "ci" not in verified:
        ci_ref = payload["attestation_bundle"].get("ci_provenance_path")
        ci_path = (
            resolve_manifest_ref(manifest_path, ci_ref, root=root)
            if ci_ref
            else provenance_path.with_name(f"{provenance_path.stem}.ci.json")
        )
        if not ci_path.exists():
            raise DistributionError(f"missing CI attestation payload: {ci_path}")
        try:
            verify_ci_attestation(ci_path, root=attestation_root)
        except AttestationError as exc:
            raise DistributionError(str(exc)) from exc
        verified.add("ci")
    if "ssh" in required and "ssh" not in verified:
        raise DistributionError("distribution manifest requires SSH attestation verification")
    result["formats_verified"] = sorted(verified)
    return result


def _actual_bundle_metadata(
    payload: dict[str, Any], signed_distribution: dict[str, Any], bundle_path: Path
) -> dict[str, Any] | None:
    signed_bundle = signed_distribution.get("bundle") or {}
    metadata_present = any(
        value
        for value in (
            payload.get("file_manifest"),
            signed_distribution.get("file_manifest"),
            payload.get("build"),
            signed_distribution.get("build"),
        )
    )
    if not metadata_present:
        return None
    return inspect_distribution_bundle(bundle_path, expected_root=signed_bundle.get("root_dir"))


def _verify_signed_core_fields(
    payload: dict[str, Any], provenance: dict[str, Any], signed_bundle: dict[str, Any]
) -> None:
    comparisons = (
        ("skill.name", payload["skill"].get("name"), provenance.get("skill", {}).get("name")),
        (
            "skill.version",
            payload["skill"].get("version"),
            provenance.get("skill", {}).get("version"),
        ),
        (
            "source_snapshot.tag",
            payload["source_snapshot"].get("tag"),
            provenance.get("source_snapshot", {}).get("tag"),
        ),
        (
            "source_snapshot.commit",
            payload["source_snapshot"].get("commit"),
            provenance.get("source_snapshot", {}).get("commit"),
        ),
        ("bundle.path", payload["bundle"].get("path"), signed_bundle.get("path")),
        ("bundle.sha256", payload["bundle"].get("sha256"), signed_bundle.get("sha256")),
        ("bundle.format", payload["bundle"].get("format"), signed_bundle.get("format")),
        ("bundle.root_dir", payload["bundle"].get("root_dir"), signed_bundle.get("root_dir")),
    )
    for label, manifest_value, signed_value in comparisons:
        if manifest_value != signed_value:
            raise DistributionError(f"{label} does not match signed attestation payload")


def _verify_file_manifest(
    payload_manifest: object, signed_manifest: object, actual_metadata: dict[str, Any] | None
) -> None:
    if isinstance(payload_manifest, list) and not payload_manifest:
        payload_manifest = None
    signed = normalize_file_manifest(signed_manifest)
    actual = normalize_file_manifest((actual_metadata or {}).get("file_manifest"))
    if payload_manifest is not None:
        manifest = normalize_file_manifest(payload_manifest)
        if manifest is None:
            raise DistributionError("distribution manifest file_manifest metadata is invalid")
        if signed is not None and manifest != signed:
            raise DistributionError("file manifest does not match signed attestation payload")
        if actual != manifest:
            raise DistributionError("file manifest does not match distribution bundle contents")
    elif signed is not None and actual != signed:
        raise DistributionError("file manifest does not match signed attestation payload")


def _verify_build_metadata(
    payload_build: object, signed_build: object, actual_metadata: dict[str, Any] | None
) -> None:
    if isinstance(payload_build, dict) and not payload_build:
        payload_build = None
    signed = normalize_build(signed_build)
    actual = normalize_build((actual_metadata or {}).get("build"), include_builder=False)
    if payload_build is not None:
        manifest = normalize_build(payload_build)
        if manifest is None:
            raise DistributionError("distribution manifest build metadata is invalid")
        if signed is not None and manifest != signed:
            raise DistributionError("build metadata does not match signed attestation payload")
        if actual != normalize_build(payload_build, include_builder=False):
            raise DistributionError("build metadata does not match distribution bundle contents")
    elif signed is not None and actual != normalize_build(signed_build, include_builder=False):
        raise DistributionError("build metadata does not match signed attestation payload")


def verify_distribution_manifest(
    manifest_path: str | Path,
    root: str | Path | None = None,
    attestation_root: str | Path | None = None,
) -> dict[str, Any]:
    resolved_root = Path(root or ROOT).resolve()
    resolved_attestation_root = Path(attestation_root or resolved_root).resolve()
    manifest_file, payload = _load_manifest(manifest_path, resolved_root)
    provenance_path, signature_path, bundle_path = _resolve_artifacts(
        manifest_file, payload, resolved_root
    )
    _verify_artifact_metadata(payload, provenance_path, signature_path, bundle_path)
    attestation = _verify_attestation_formats(
        manifest_file,
        payload,
        provenance_path,
        resolved_root,
        resolved_attestation_root,
    )
    provenance = load_json(provenance_path)
    signed_distribution = provenance.get("distribution") or {}
    signed_bundle = signed_distribution.get("bundle") or {}
    if not signed_bundle:
        raise DistributionError("attestation is missing distribution.bundle metadata")
    actual = _actual_bundle_metadata(payload, signed_distribution, bundle_path)
    _verify_signed_core_fields(payload, provenance, signed_bundle)
    _verify_file_manifest(
        payload.get("file_manifest"), signed_distribution.get("file_manifest"), actual
    )
    _verify_build_metadata(payload.get("build"), signed_distribution.get("build"), actual)
    if payload.get("registry") != provenance.get("registry"):
        raise DistributionError("registry context does not match signed attestation payload")
    if payload.get("dependencies") != provenance.get("dependencies"):
        raise DistributionError("dependency context does not match signed attestation payload")
    return {
        "verified": True,
        "manifest_path": str(manifest_file),
        "bundle_path": str(bundle_path),
        "provenance_path": str(provenance_path),
        "signature_path": str(signature_path),
        "skill": payload.get("skill", {}).get("name"),
        "version": payload.get("skill", {}).get("version"),
        "source_type": "distribution-manifest",
        "attestation": attestation,
        "manifest": payload,
        "provenance": provenance,
    }
