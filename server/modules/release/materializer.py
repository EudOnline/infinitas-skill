"""Release materializer — public orchestration entry point.

This module coordinates the full release materialization pipeline:
bundle creation, provenance generation, SSH signing, and artifact storage.

The implementation is split across focused sub-modules:

- :mod:`snapshot_accessors` — snapshot field accessors
- :mod:`bundle` — bundle construction and artifact path helpers
- :mod:`provenance` — provenance JSON document building
- :mod:`signing` — SSH signing and identity resolution
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from infinitas_skill.install.distribution import (
    DistributionError,
    build_distribution_manifest_payload,
    verify_distribution_manifest,
)
from infinitas_skill.release.attestation import (
    load_attestation_config,
    resolve_attestation_key,
)
from server.artifact_ops import sha256_bytes
from server.modules.release import service

# Sub-modules — the actual implementations
from server.modules.release.bundle import bundle_bytes, uploaded_bundle_data
from server.modules.release.models import Artifact, Release
from server.modules.release.provenance import build_provenance_payload
from server.modules.release.signing import resolve_signer_identity, sign_provenance
from server.modules.release.snapshot_accessors import (
    snapshot_content_artifact_id,
    snapshot_content_mode,
    snapshot_content_ref,
    snapshot_metadata,
)
from server.modules.release.storage import ArtifactStorage, build_artifact_storage

# Backward-compatible re-exports for any code that imported these from materializer
# We use a leading underscore convention for private helpers that moved.
# Public API remains: materialize_release(), release_requires_materialization()
__all__ = ["materialize_release", "release_requires_materialization"]


def _materialize_bundle(
    db: Session,
    *,
    snapshot,
    artifact_root: Path,
) -> tuple[bytes, int, str]:
    metadata = snapshot_metadata(snapshot)
    content_mode = snapshot_content_mode(snapshot)
    content_ref = snapshot_content_ref(snapshot)
    if content_mode == "uploaded_bundle":
        return uploaded_bundle_data(
            db,
            artifact_root=artifact_root,
            content_artifact_id=snapshot_content_artifact_id(snapshot),
        )
    return (
        *bundle_bytes(
            skill_slug=snapshot.skill.slug,
            content_ref=content_ref,
            metadata=metadata,
        ),
        snapshot.skill.slug,
    )


def materialize_release(
    db: Session,
    *,
    release_id: int,
    artifact_root: Path,
    repo_root: Path,
    storage_backend: ArtifactStorage | None = None,
) -> tuple[Release, list[Artifact]]:
    snapshot = service.get_release_snapshot(db, release_id)
    release = snapshot.release
    existing_artifacts = service.get_artifacts_for_release(db, release.id)

    # Check if existing materialization is still current
    if (
        release.state == "ready"
        and release.manifest_artifact_id is not None
        and release.bundle_artifact_id is not None
        and release.signature_artifact_id is not None
        and release.provenance_artifact_id is not None
        and len(existing_artifacts) >= 4
        and _existing_materialization_is_current(
            snapshot=snapshot,
            release=release,
            existing_artifacts=existing_artifacts,
            artifact_root=artifact_root,
            repo_root=Path(repo_root).resolve(),
        )
    ):
        return release, existing_artifacts

    publisher = snapshot.namespace.slug
    skill_slug = snapshot.skill.slug
    version = snapshot.skill_version.version
    storage = storage_backend or build_artifact_storage(artifact_root)

    # Build bundle
    bundle_data, bundle_file_count, bundle_root_dir = _materialize_bundle(
        db, snapshot=snapshot, artifact_root=artifact_root
    )
    bundle_sha256 = sha256_bytes(bundle_data)

    # Public paths
    skill_dir = Path("skills") / publisher / skill_slug / version
    bundle_public_path = skill_dir / "skill.tar.gz"
    manifest_public_path = skill_dir / "manifest.json"

    # Store bundle
    storage.put_bytes(bundle_data, public_path=str(bundle_public_path))

    # Load attestation config and signing key
    repo_root = Path(repo_root).resolve()
    attestation_cfg = load_attestation_config(repo_root)
    signing_key = resolve_attestation_key(repo_root, attestation_cfg)
    signer_identity = resolve_signer_identity(
        repo_root=repo_root,
        allowed_signers_path=repo_root / attestation_cfg["allowed_signers_rel"],
        signing_key=signing_key,
    )

    # Build and sign provenance
    signature_filename = (
        f"{publisher}--{skill_slug}-{version}.json"
        + attestation_cfg["signature_ext"]
    )
    provenance = build_provenance_payload(
        snapshot=snapshot,
        release=release,
        repo_root=repo_root,
        bundle_public_path=str(bundle_public_path),
        manifest_public_path=str(manifest_public_path),
        bundle_sha256=bundle_sha256,
        bundle_size=len(bundle_data),
        bundle_root_dir=bundle_root_dir,
        bundle_file_count=bundle_file_count,
        signature_filename=signature_filename,
        attestation_cfg=attestation_cfg,
        signer_identity=signer_identity,
    )

    from server.modules.release.bundle import canonical_json_bytes as _canonical_json
    provenance_bytes = _canonical_json(provenance)

    signature_bytes = sign_provenance(
        provenance_bytes=provenance_bytes,
        provenance_filename=f"{publisher}--{skill_slug}-{version}.json",
        signing_key=signing_key,
        namespace=attestation_cfg["namespace"],
        signature_ext=attestation_cfg["signature_ext"],
    )

    # Store provenance and signature
    provenance_public_path = (
        Path("provenance") / f"{publisher}--{skill_slug}-{version}.json"
    )
    signature_public_path = Path(
        f"provenance/{publisher}--{skill_slug}-{version}.json"
        + attestation_cfg["signature_ext"]
    )
    storage.put_bytes(provenance_bytes, public_path=str(provenance_public_path))
    storage.put_bytes(signature_bytes, public_path=str(signature_public_path))

    # Build distribution manifest from on-disk provenance and bundle
    provenance_disk_path = artifact_root / provenance_public_path
    bundle_disk_path = artifact_root / bundle_public_path
    manifest = build_distribution_manifest_payload(
        provenance_disk_path,
        bundle_disk_path,
        root=artifact_root,
        attestation_root=repo_root,
    )
    manifest_bytes = _canonical_json(manifest)
    storage.put_bytes(manifest_bytes, public_path=str(manifest_public_path))

    # Upsert artifacts in DB
    bundle_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="bundle",
        storage_uri=str(bundle_public_path),
        sha256=bundle_sha256,
        size_bytes=len(bundle_data),
    )
    manifest_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="manifest",
        storage_uri=str(manifest_public_path),
        sha256=sha256_bytes(manifest_bytes),
        size_bytes=len(manifest_bytes),
    )
    provenance_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="provenance",
        storage_uri=str(provenance_public_path),
        sha256=sha256_bytes(provenance_bytes),
        size_bytes=len(provenance_bytes),
    )
    signature_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="signature",
        storage_uri=str(signature_public_path),
        sha256=sha256_bytes(signature_bytes),
        size_bytes=len(signature_bytes),
    )

    # Collect platform compatibility (optional — hosted skills may not exist on disk)
    from infinitas_skill.release.release_resolution import resolve_skill
    from infinitas_skill.release.service import collect_release_state

    platform_compat = None
    try:
        resolved_skill = resolve_skill(repo_root, skill_slug)
        release_state = collect_release_state(resolved_skill, root=repo_root)
        platform_compat = release_state.get("platform_compatibility")
    except Exception:
        pass

    db.refresh(release)
    service.mark_release_ready(
        db,
        release=release,
        manifest_artifact_id=manifest_artifact.id,
        bundle_artifact_id=bundle_artifact.id,
        signature_artifact_id=signature_artifact.id,
        provenance_artifact_id=provenance_artifact.id,
    )

    return service.get_release_or_404(db, release.id), service.get_artifacts_for_release(
        db, release.id
    )


def release_requires_materialization(
    db: Session,
    *,
    release_id: int,
    artifact_root: Path,
    repo_root: Path,
) -> bool:
    snapshot = service.get_release_snapshot(db, release_id)
    release = snapshot.release
    existing_artifacts = service.get_artifacts_for_release(db, release.id)
    return not _existing_materialization_is_current(
        snapshot=snapshot,
        release=release,
        existing_artifacts=existing_artifacts,
        artifact_root=artifact_root,
        repo_root=Path(repo_root).resolve(),
    )


def _existing_materialization_is_current(
    *,
    snapshot,
    release: Release,
    existing_artifacts: list[Artifact],
    artifact_root: Path,
    repo_root: Path,
) -> bool:
    if (
        release.state != "ready"
        or release.manifest_artifact_id is None
        or release.bundle_artifact_id is None
        or release.signature_artifact_id is None
        or release.provenance_artifact_id is None
        or len(existing_artifacts) < 4
    ):
        return False

    publisher = snapshot.namespace.slug
    skill_slug = snapshot.skill.slug
    version = snapshot.skill_version.version
    manifest_path = (
        Path(artifact_root).resolve()
        / "skills"
        / publisher
        / skill_slug
        / version
        / "manifest.json"
    )
    try:
        verified = verify_distribution_manifest(
            manifest_path,
            root=artifact_root,
            attestation_root=repo_root,
        )
    except DistributionError:
        return False
    if not bool(verified.get("verified")):
        return False
    return _artifact_rows_match_materialized_files(
        release=release,
        existing_artifacts=existing_artifacts,
        artifact_root=artifact_root,
        publisher=publisher,
        skill_slug=skill_slug,
        version=version,
    )


def _artifact_rows_match_materialized_files(
    *,
    release: Release,
    existing_artifacts: list[Artifact],
    artifact_root: Path,
    publisher: str,
    skill_slug: str,
    version: str,
) -> bool:
    paths_by_kind = {
        "bundle": (
            Path(artifact_root)
            / "skills"
            / publisher
            / skill_slug
            / version
            / "skill.tar.gz"
        ),
        "manifest": (
            Path(artifact_root)
            / "skills"
            / publisher
            / skill_slug
            / version
            / "manifest.json"
        ),
        "provenance": (
            Path(artifact_root)
            / "provenance"
            / f"{publisher}--{skill_slug}-{version}.json"
        ),
        "signature": Path(artifact_root)
        / "provenance"
        / f"{publisher}--{skill_slug}-{version}.json.ssig",
    }
    release_artifact_ids = {
        "bundle": release.bundle_artifact_id,
        "manifest": release.manifest_artifact_id,
        "provenance": release.provenance_artifact_id,
        "signature": release.signature_artifact_id,
    }
    artifacts_by_id = {int(item.id): item for item in existing_artifacts}

    for kind, path in paths_by_kind.items():
        artifact_id = release_artifact_ids.get(kind)
        if artifact_id is None:
            return False
        artifact = artifacts_by_id.get(int(artifact_id))
        if artifact is None or str(artifact.kind) != kind:
            return False
        if not path.is_file():
            return False
        raw = path.read_bytes()
        if sha256_bytes(raw) != artifact.sha256:
            return False
        if len(raw) != int(artifact.size_bytes or 0):
            return False
    return True
