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

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

import server.modules.release.service as service
from infinitas_skill.install.distribution_core import DistributionError
from infinitas_skill.install.distribution_materialization import (
    build_distribution_manifest_payload,
)
from infinitas_skill.install.distribution_verification import verify_distribution_manifest
from infinitas_skill.release.attestation import (
    load_attestation_config,
    resolve_attestation_key,
)
from server.artifact_ops import sha256_bytes

# Sub-modules — the actual implementations
from server.modules.release.bundle import bundle_bytes, uploaded_bundle_data
from server.modules.release.models import Artifact, Release
from server.modules.release.provenance import build_provenance_payload
from server.modules.release.service import ReleaseSnapshot
from server.modules.release.signing import resolve_signer_identity, sign_provenance
from server.modules.release.snapshot_accessors import (
    snapshot_content_artifact_id,
    snapshot_content_mode,
    snapshot_content_ref,
    snapshot_metadata,
)
from server.modules.release.storage import ArtifactStorage, build_artifact_storage

logger = logging.getLogger(__name__)

__all__ = ["materialize_release", "release_requires_materialization"]


def _checkpoint_heartbeat(heartbeat: Callable[[], None] | None) -> None:
    if heartbeat is not None:
        heartbeat()


def _materialize_bundle(
    db: Session,
    *,
    snapshot: ReleaseSnapshot,
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


def _ready_materialization_is_current(
    *,
    snapshot: ReleaseSnapshot,
    release: Release,
    artifacts: list[Artifact],
    artifact_root: Path,
    repo_root: Path,
) -> bool:
    artifact_ids_present = all(
        artifact_id is not None
        for artifact_id in (
            release.manifest_artifact_id,
            release.bundle_artifact_id,
            release.signature_artifact_id,
            release.provenance_artifact_id,
        )
    )
    return (
        release.state == "ready"
        and artifact_ids_present
        and len(artifacts) >= 4
        and _existing_materialization_is_current(
            snapshot=snapshot,
            release=release,
            existing_artifacts=artifacts,
            artifact_root=artifact_root,
            repo_root=repo_root,
        )
    )


def _build_and_store_bundle(
    db: Session,
    *,
    snapshot: ReleaseSnapshot,
    artifact_root: Path,
    storage: ArtifactStorage,
) -> dict[str, Any]:
    data, file_count, root_dir = _materialize_bundle(
        db, snapshot=snapshot, artifact_root=artifact_root
    )
    sha256 = sha256_bytes(data)
    public_path = (
        Path("skills")
        / snapshot.namespace.slug
        / snapshot.skill.slug
        / snapshot.skill_version.version
        / "skill.tar.gz"
    )
    storage.put_bytes(data, public_path=str(public_path))
    return {
        "data": data,
        "file_count": file_count,
        "root_dir": root_dir,
        "sha256": sha256,
        "public_path": public_path,
    }


def _build_and_store_provenance(
    *,
    snapshot: ReleaseSnapshot,
    release: Release,
    repo_root: Path,
    storage: ArtifactStorage,
    bundle: dict[str, Any],
) -> dict[str, Any]:
    from server.modules.release.bundle import canonical_json_bytes

    publisher = snapshot.namespace.slug
    skill_slug = snapshot.skill.slug
    version = snapshot.skill_version.version
    manifest_path = Path("skills") / publisher / skill_slug / version / "manifest.json"
    config = load_attestation_config(repo_root)
    signing_key = resolve_attestation_key(repo_root, config)
    signer = resolve_signer_identity(
        repo_root=repo_root,
        allowed_signers_path=repo_root / config["allowed_signers_rel"],
        signing_key=signing_key,
    )
    filename = f"{publisher}--{skill_slug}-{version}.json"
    provenance = build_provenance_payload(
        snapshot=snapshot,
        release=release,
        repo_root=repo_root,
        bundle_public_path=str(bundle["public_path"]),
        manifest_public_path=str(manifest_path),
        bundle_sha256=bundle["sha256"],
        bundle_size=len(bundle["data"]),
        bundle_root_dir=bundle["root_dir"],
        bundle_file_count=bundle["file_count"],
        signature_filename=filename + config["signature_ext"],
        attestation_cfg=config,
        signer_identity=signer,
    )
    provenance_bytes = canonical_json_bytes(provenance)
    signature_bytes = sign_provenance(
        provenance_bytes=provenance_bytes,
        provenance_filename=filename,
        signing_key=signing_key,
        namespace=config["namespace"],
        signature_ext=config["signature_ext"],
    )
    public_path = Path("provenance") / filename
    signature_path = Path(f"provenance/{filename}" + config["signature_ext"])
    storage.put_bytes(provenance_bytes, public_path=str(public_path))
    storage.put_bytes(signature_bytes, public_path=str(signature_path))
    return {
        "bytes": provenance_bytes,
        "signature_bytes": signature_bytes,
        "public_path": public_path,
        "signature_path": signature_path,
        "manifest_path": manifest_path,
    }


def _build_and_store_manifest(
    *,
    artifact_root: Path,
    repo_root: Path,
    storage: ArtifactStorage,
    bundle: dict,
    provenance: dict,
) -> dict:
    from server.modules.release.bundle import canonical_json_bytes

    payload = build_distribution_manifest_payload(
        artifact_root / provenance["public_path"],
        artifact_root / bundle["public_path"],
        root=artifact_root,
        attestation_root=repo_root,
    )
    data = canonical_json_bytes(payload)
    storage.put_bytes(data, public_path=str(provenance["manifest_path"]))
    return {"bytes": data, "public_path": provenance["manifest_path"]}


def _upsert_materialized_artifacts(
    db: Session, *, release: Release, bundle: dict, provenance: dict, manifest: dict
) -> dict[str, Artifact]:
    specifications = {
        "bundle": (bundle["public_path"], bundle["sha256"], bundle["data"]),
        "manifest": (manifest["public_path"], sha256_bytes(manifest["bytes"]), manifest["bytes"]),
        "provenance": (
            provenance["public_path"],
            sha256_bytes(provenance["bytes"]),
            provenance["bytes"],
        ),
        "signature": (
            provenance["signature_path"],
            sha256_bytes(provenance["signature_bytes"]),
            provenance["signature_bytes"],
        ),
    }
    return {
        kind: service.upsert_artifact(
            db,
            release_id=release.id,
            kind=kind,
            storage_uri=str(path),
            sha256=digest,
            size_bytes=len(data),
        )
        for kind, (path, digest, data) in specifications.items()
    }


def _collect_platform_compatibility(repo_root: Path, skill_slug: str, release: Release) -> None:
    from infinitas_skill.release.release_resolution import resolve_skill
    from infinitas_skill.release.service import collect_release_state

    try:
        resolved_skill = resolve_skill(repo_root, skill_slug)
        collect_release_state(resolved_skill, root=repo_root).get("platform_compatibility")
    except Exception:
        logger.warning(
            "Platform compatibility collection failed for %s (release_id=%s); "
            "proceeding without compatibility data",
            skill_slug,
            release.id,
            exc_info=True,
        )


def materialize_release(
    db: Session,
    *,
    release_id: int,
    artifact_root: Path,
    repo_root: Path,
    storage_backend: ArtifactStorage | None = None,
    heartbeat: Callable[[], None] | None = None,
) -> tuple[Release, list[Artifact]]:
    """Generate, sign, store, and register all artifacts for one release."""
    snapshot = service.get_release_snapshot(db, release_id)
    release = snapshot.release
    existing_artifacts = service.get_artifacts_for_release(db, release.id)
    resolved_repo_root = Path(repo_root).resolve()
    if _ready_materialization_is_current(
        snapshot=snapshot,
        release=release,
        artifacts=existing_artifacts,
        artifact_root=artifact_root,
        repo_root=resolved_repo_root,
    ):
        return release, existing_artifacts
    storage = storage_backend or build_artifact_storage(artifact_root)
    _checkpoint_heartbeat(heartbeat)
    bundle = _build_and_store_bundle(
        db, snapshot=snapshot, artifact_root=artifact_root, storage=storage
    )
    _checkpoint_heartbeat(heartbeat)
    provenance = _build_and_store_provenance(
        snapshot=snapshot,
        release=release,
        repo_root=resolved_repo_root,
        storage=storage,
        bundle=bundle,
    )
    _checkpoint_heartbeat(heartbeat)
    manifest = _build_and_store_manifest(
        artifact_root=artifact_root,
        repo_root=resolved_repo_root,
        storage=storage,
        bundle=bundle,
        provenance=provenance,
    )
    _checkpoint_heartbeat(heartbeat)
    _collect_platform_compatibility(resolved_repo_root, snapshot.skill.slug, release)
    _checkpoint_heartbeat(heartbeat)
    artifacts = _upsert_materialized_artifacts(
        db, release=release, bundle=bundle, provenance=provenance, manifest=manifest
    )
    db.refresh(release)
    service.mark_release_ready(
        db,
        release=release,
        manifest_artifact_id=artifacts["manifest"].id,
        bundle_artifact_id=artifacts["bundle"].id,
        signature_artifact_id=artifacts["signature"].id,
        provenance_artifact_id=artifacts["provenance"].id,
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
    snapshot: ReleaseSnapshot,
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
            Path(artifact_root) / "skills" / publisher / skill_slug / version / "skill.tar.gz"
        ),
        "manifest": (
            Path(artifact_root) / "skills" / publisher / skill_slug / version / "manifest.json"
        ),
        "provenance": (
            Path(artifact_root) / "provenance" / f"{publisher}--{skill_slug}-{version}.json"
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
