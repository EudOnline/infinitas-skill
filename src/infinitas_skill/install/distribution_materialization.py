"""Materialization and catalog projections for distribution manifests."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from infinitas_skill.hashing import sha256_file
from infinitas_skill.install.distribution_core import (
    DistributionError,
    inspect_distribution_bundle,
    installed_integrity_capability_summary,
    load_json,
    relative_from_root,
    reproducibility_summary,
)
from infinitas_skill.install.distribution_index import (
    load_distribution_index as _load_distribution_index,
)
from infinitas_skill.install.distribution_validation import validate_distribution_manifest
from infinitas_skill.install.distribution_verification import verify_distribution_manifest
from infinitas_skill.install.http_registry import fetch_binary
from infinitas_skill.release.attestation import load_attestation_config
from infinitas_skill.release.state import ROOT


def safely_extract_bundle(
    bundle_path: str | Path,
    destination_root: str | Path,
    expected_root: str | None = None,
) -> Path:
    import tarfile

    bundle = Path(bundle_path).resolve()
    destination = Path(destination_root).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(bundle, mode="r:gz") as archive:
        safe_members = []
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise DistributionError(f"symlink in bundle is not allowed: {member.name}")
            if not member.isfile() and not member.isdir():
                continue
            resolved = (destination / member.name).resolve()
            if not resolved.is_relative_to(destination):
                raise DistributionError(f"unsafe bundle member path: {member.name}")
            safe_members.append(member)
        archive.extractall(destination, members=safe_members, filter="data")
    if expected_root:
        source_dir = destination / expected_root
        if not source_dir.is_dir():
            raise DistributionError(f"expected extracted bundle root {expected_root} is missing")
        return source_dir
    dirs = [path for path in destination.iterdir() if path.is_dir()]
    if len(dirs) != 1:
        raise DistributionError(f"expected one extracted top-level directory, found {len(dirs)}")
    return dirs[0]


def _local_materialization_fields(
    info: dict[str, Any], payload: dict[str, Any], root: Path, manifest_path: str | Path
) -> dict[str, Any]:
    bundle = payload.get("bundle") or {}
    attestation = payload.get("attestation_bundle") or {}
    snapshot = payload.get("source_snapshot") or {}
    return {
        "distribution_manifest": relative_from_root(root, manifest_path),
        "distribution_bundle_sha256": bundle.get("sha256"),
        "distribution_bundle_size": bundle.get("size"),
        "distribution_bundle_root_dir": bundle.get("root_dir"),
        "distribution_bundle_file_count": bundle.get("file_count"),
        "distribution_attestation": attestation.get("provenance_path"),
        "distribution_attestation_signature": attestation.get("signature_path"),
        "distribution_attestation_sha256": attestation.get("provenance_sha256"),
        "distribution_attestation_signature_sha256": attestation.get("signature_sha256"),
        "source_snapshot_kind": snapshot.get("kind"),
        "source_snapshot_tag": snapshot.get("tag"),
        "source_snapshot_ref": snapshot.get("ref"),
        "source_snapshot_commit": snapshot.get("commit"),
        "source_stage": (payload.get("skill") or {}).get("status") or info.get("stage"),
        "registry_context": payload.get("registry"),
        "dependency_context": payload.get("dependencies"),
    }


def materialize_distribution_source(
    source_info: Mapping[str, Any] | None, root: str | Path | None = None
) -> dict[str, Any]:
    resolved_root = Path(root or ROOT).resolve()
    info = dict(source_info or {})
    if (info.get("source_type") or "working-tree") != "distribution-manifest":
        path = info.get("skill_path") or info.get("path")
        if not path:
            raise DistributionError("working-tree source is missing path")
        info.update({"materialized_path": path, "cleanup_dir": None})
        return info
    manifest_path = info.get("distribution_manifest") or info.get("path")
    if not manifest_path:
        raise DistributionError("distribution-manifest source is missing manifest path")
    if info.get("registry_kind") == "http":
        return _materialize_remote_distribution_source(info)
    verified = verify_distribution_manifest(manifest_path, root=resolved_root)
    payload = verified["manifest"]
    bundle = payload.get("bundle") or {}
    expected_sha = info.get("distribution_bundle_sha256")
    if expected_sha and bundle.get("sha256") and expected_sha != bundle.get("sha256"):
        raise DistributionError("bundle digest does not match registry metadata")
    temp_root = Path(tempfile.mkdtemp(prefix="infinitas-distribution-"))
    materialized = safely_extract_bundle(
        verified["bundle_path"], temp_root, expected_root=bundle.get("root_dir")
    )
    info.update(
        {
            "materialized_path": str(materialized),
            "cleanup_dir": str(temp_root),
            "distribution_bundle": relative_from_root(resolved_root, verified["bundle_path"]),
            **_local_materialization_fields(info, payload, resolved_root, manifest_path),
        }
    )
    return info


def _download_remote_ref(
    base_url: str,
    rel_path: str,
    temp_root: str | Path,
    *,
    token_env: str | None = None,
) -> Path:
    ref_path = Path(rel_path)
    if ref_path.is_absolute():
        raise DistributionError(f"hosted artifact path must be relative: {rel_path}")
    root = Path(temp_root).resolve()
    output = (root / ref_path).resolve()
    if not output.is_relative_to(root):
        raise DistributionError(f"unsafe hosted artifact path: {rel_path}")
    fetch_binary(base_url, rel_path, output, token_env=token_env)
    return output


def _materialize_remote_distribution_source(info: dict[str, Any]) -> dict[str, Any]:
    base_url = info.get("registry_base_url") or info.get("registry_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise DistributionError("hosted distribution source is missing registry_base_url")
    token_value = (
        info.get("registry_auth_env") if info.get("registry_auth_mode") == "token" else None
    )
    token_env = token_value if isinstance(token_value, str) else None
    manifest_ref = info.get("distribution_manifest") or info.get("path")
    if not isinstance(manifest_ref, str):
        raise DistributionError("hosted distribution source is missing manifest path")
    temp_root = Path(tempfile.mkdtemp(prefix="infinitas-http-distribution-"))
    manifest_path = _download_remote_ref(base_url, manifest_ref, temp_root, token_env=token_env)
    payload = load_json(manifest_path)
    bundle_ref = (payload.get("bundle") or {}).get("path")
    attestation = payload.get("attestation_bundle") or {}
    provenance_ref = attestation.get("provenance_path")
    signature_ref = attestation.get("signature_path")
    refs = (bundle_ref, provenance_ref, signature_ref)
    if not all(isinstance(ref, str) and ref for ref in refs):
        raise DistributionError("hosted manifest is missing bundle or attestation references")
    for ref in (str(bundle_ref), str(provenance_ref), str(signature_ref)):
        _download_remote_ref(base_url, ref, temp_root, token_env=token_env)
    verified = verify_distribution_manifest(manifest_path, root=temp_root, attestation_root=ROOT)
    manifest_payload = verified["manifest"]
    bundle = manifest_payload.get("bundle") or {}
    bundle_sha = bundle.get("sha256")
    expected_sha = info.get("distribution_bundle_sha256")
    if expected_sha and bundle_sha and expected_sha != bundle_sha:
        raise DistributionError("bundle digest does not match registry metadata")
    materialized = safely_extract_bundle(
        verified["bundle_path"], temp_root / "__materialized__", bundle.get("root_dir")
    )
    info.update(
        {
            "materialized_path": str(materialized),
            "cleanup_dir": str(temp_root),
            "distribution_manifest": manifest_ref,
            "distribution_bundle": bundle_ref,
            "distribution_bundle_sha256": bundle_sha,
            "distribution_bundle_size": bundle.get("size"),
            "distribution_bundle_root_dir": bundle.get("root_dir"),
            "distribution_bundle_file_count": bundle.get("file_count"),
            "distribution_attestation": provenance_ref,
            "distribution_attestation_signature": signature_ref,
            "distribution_attestation_sha256": attestation.get("provenance_sha256"),
            "distribution_attestation_signature_sha256": attestation.get("signature_sha256"),
            "source_snapshot_kind": (manifest_payload.get("source_snapshot") or {}).get("kind"),
            "source_snapshot_tag": (manifest_payload.get("source_snapshot") or {}).get("tag"),
            "source_snapshot_ref": (manifest_payload.get("source_snapshot") or {}).get("ref"),
            "source_snapshot_commit": (manifest_payload.get("source_snapshot") or {}).get("commit"),
            "source_stage": (manifest_payload.get("skill") or {}).get("status")
            or info.get("stage"),
            "registry_context": manifest_payload.get("registry"),
            "dependency_context": manifest_payload.get("dependencies"),
        }
    )
    return info


def manifest_index_entry(manifest_path: str | Path, root: str | Path) -> dict[str, Any]:
    payload = load_json(manifest_path)
    errors = validate_distribution_manifest(payload)
    if errors:
        raise DistributionError(f"{manifest_path}: " + "; ".join(errors))
    skill = payload.get("skill") or {}
    bundle = payload.get("bundle") or {}
    attestation = payload.get("attestation_bundle") or {}
    reproducibility = reproducibility_summary(payload)
    integrity = installed_integrity_capability_summary(payload)
    snapshot = payload.get("source_snapshot") or {}
    return {
        "name": skill.get("name"),
        "publisher": skill.get("publisher"),
        "qualified_name": skill.get("qualified_name"),
        "identity_mode": skill.get("identity_mode"),
        "version": skill.get("version"),
        "status": skill.get("status"),
        "summary": skill.get("summary"),
        "manifest_path": relative_from_root(root, manifest_path),
        "bundle_path": bundle.get("path"),
        "bundle_sha256": bundle.get("sha256"),
        "bundle_size": bundle.get("size"),
        "bundle_file_count": bundle.get("file_count"),
        "bundle_root_dir": bundle.get("root_dir"),
        "attestation_path": attestation.get("provenance_path"),
        "attestation_signature_path": attestation.get("signature_path"),
        "attestation_sha256": attestation.get("provenance_sha256"),
        "attestation_signature_sha256": attestation.get("signature_sha256"),
        "signer_identity": attestation.get("signer_identity"),
        "namespace": attestation.get("namespace"),
        "allowed_signers": attestation.get("allowed_signers"),
        "file_manifest_count": reproducibility.get("file_manifest_count"),
        "build_archive_format": reproducibility.get("build_archive_format"),
        "installed_integrity_capability": integrity.get("installed_integrity_capability"),
        "installed_integrity_reason": integrity.get("installed_integrity_reason"),
        "source_snapshot_kind": snapshot.get("kind"),
        "source_snapshot_tag": snapshot.get("tag"),
        "source_snapshot_ref": snapshot.get("ref"),
        "source_snapshot_commit": snapshot.get("commit"),
        "registry": payload.get("registry"),
        "dependencies": payload.get("dependencies"),
        "depends_on": skill.get("depends_on", []),
        "conflicts_with": skill.get("conflicts_with", []),
        "generated_at": payload.get("generated_at"),
        "source_type": "distribution-manifest",
    }


def load_distribution_index(root: str | Path) -> list[dict[str, Any]]:
    return _load_distribution_index(root)


def build_distribution_manifest_payload(
    provenance_path: str | Path,
    bundle_path: str | Path,
    root: str | Path | None = None,
    attestation_root: str | Path | None = None,
) -> dict[str, Any]:
    resolved_root = Path(root or ROOT).resolve()
    resolved_attestation_root = Path(attestation_root or resolved_root).resolve()
    provenance_file = Path(provenance_path).resolve()
    bundle_file = Path(bundle_path).resolve()
    provenance = load_json(provenance_file)
    distribution = provenance.get("distribution") or {}
    signed_bundle = distribution.get("bundle") or {}
    if not signed_bundle:
        raise DistributionError("attestation payload is missing distribution.bundle metadata")
    bundle_metadata = inspect_distribution_bundle(
        bundle_file, expected_root=signed_bundle.get("root_dir")
    )
    signature_path = provenance_file.with_suffix(
        provenance_file.suffix + (provenance.get("attestation") or {}).get("signature_ext", ".ssig")
    )
    if not signature_path.exists():
        raise DistributionError(f"missing attestation signature: {signature_path}")
    required_formats = ["ssh"]
    if load_attestation_config(resolved_attestation_root).get("requires_ci_attestation"):
        required_formats.append("ci")
    skill = provenance.get("skill") or {}
    payload: dict[str, Any] = {
        "$schema": "schemas/distribution-manifest.schema.json",
        "schema_version": 1,
        "kind": "skill-distribution-manifest",
        "generated_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "skill": {
            key: skill.get(key)
            for key in (
                "name",
                "publisher",
                "qualified_name",
                "identity_mode",
                "version",
                "status",
                "summary",
                "author",
                "owners",
                "maintainers",
                "depends_on",
                "conflicts_with",
            )
        },
        "source_snapshot": provenance.get("source_snapshot"),
        "bundle": {
            key: signed_bundle.get(key)
            for key in ("path", "format", "sha256", "size", "root_dir", "file_count")
        },
        "file_manifest": distribution.get("file_manifest")
        or bundle_metadata.get("file_manifest", []),
        "build": distribution.get("build") or bundle_metadata.get("build"),
        "registry": provenance.get("registry"),
        "dependencies": provenance.get("dependencies"),
        "attestation_bundle": {
            "provenance_path": relative_from_root(resolved_root, provenance_file),
            "provenance_sha256": sha256_file(provenance_file),
            "signature_path": relative_from_root(resolved_root, signature_path),
            "signature_sha256": sha256_file(signature_path),
            "signer_identity": (provenance.get("attestation") or {}).get("signer_identity"),
            "namespace": (provenance.get("attestation") or {}).get("namespace"),
            "allowed_signers": (provenance.get("attestation") or {}).get("allowed_signers"),
            "required_formats": required_formats,
        },
    }
    ci_path = provenance_file.with_name(f"{provenance_file.stem}.ci.json")
    if ci_path.exists():
        payload["attestation_bundle"]["ci_provenance_path"] = relative_from_root(
            resolved_root, ci_path
        )
        payload["attestation_bundle"]["ci_provenance_sha256"] = sha256_file(ci_path)
    return payload
