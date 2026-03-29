from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path

from sqlalchemy.orm import Session

from server.modules.authoring.service import load_metadata
from server.modules.release import service
from server.modules.release.models import Artifact, Release
from server.modules.release.storage import ArtifactStorage, build_artifact_storage


def _canonical_json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _bundle_bytes(*, skill_slug: str, content_ref: str, metadata: dict) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gzip_file:
        with tarfile.open(fileobj=gzip_file, mode="w", format=tarfile.PAX_FORMAT) as archive:
            entries = {
                f"{skill_slug}/snapshot/content-ref.txt": (content_ref.rstrip("\n") + "\n").encode("utf-8"),
                f"{skill_slug}/snapshot/metadata.json": _canonical_json_bytes(metadata),
            }
            for path, raw in entries.items():
                info = tarfile.TarInfo(name=path)
                info.size = len(raw)
                info.mtime = 0
                info.mode = 0o644
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue()


def materialize_release(
    db: Session,
    *,
    release_id: int,
    artifact_root: Path,
    storage_backend: ArtifactStorage | None = None,
) -> tuple[Release, list[Artifact]]:
    snapshot = service.get_release_snapshot(db, release_id)
    release = snapshot.release
    existing_artifacts = service.get_artifacts_for_release(db, release.id)
    if (
        release.state == "ready"
        and release.manifest_artifact_id is not None
        and release.bundle_artifact_id is not None
        and release.signature_artifact_id is not None
        and release.provenance_artifact_id is not None
        and len(existing_artifacts) >= 4
    ):
        return release, existing_artifacts

    metadata = load_metadata(snapshot.draft.metadata_json)
    publisher = snapshot.namespace.slug
    version = snapshot.skill_version.version
    skill_slug = snapshot.skill.slug
    provenance_basename = f"{publisher}--{skill_slug}-{version}.json"

    bundle_public_path = f"skills/{publisher}/{skill_slug}/{version}/skill.tar.gz"
    manifest_public_path = f"skills/{publisher}/{skill_slug}/{version}/manifest.json"
    provenance_public_path = f"provenance/{provenance_basename}"
    signature_public_path = f"provenance/{provenance_basename}.ssig"

    storage = storage_backend or build_artifact_storage(artifact_root)
    bundle_bytes = _bundle_bytes(
        skill_slug=skill_slug,
        content_ref=snapshot.draft.content_ref,
        metadata=metadata,
    )
    stored_bundle = storage.put_bytes(bundle_bytes, public_path=bundle_public_path)

    provenance_payload = {
        "schema_version": 1,
        "kind": "private-skill-release-provenance",
        "release": {
            "id": release.id,
            "format_version": release.format_version,
            "skill_version_id": snapshot.skill_version.id,
        },
        "skill": {
            "publisher": publisher,
            "name": skill_slug,
            "qualified_name": f"{publisher}/{skill_slug}",
            "display_name": snapshot.skill.display_name,
            "summary": snapshot.skill.summary,
            "version": version,
        },
        "draft": {
            "id": snapshot.draft.id,
            "content_ref": snapshot.draft.content_ref,
            "metadata": metadata,
        },
        "digests": {
            "content_digest": snapshot.skill_version.content_digest,
            "metadata_digest": snapshot.skill_version.metadata_digest,
            "bundle_sha256": stored_bundle.sha256,
        },
    }
    provenance_bytes = _canonical_json_bytes(provenance_payload)
    stored_provenance = storage.put_bytes(provenance_bytes, public_path=provenance_public_path)

    signature_payload = {
        "kind": "private-skill-release-signature",
        "algorithm": "sha256",
        "provenance_sha256": stored_provenance.sha256,
    }
    signature_bytes = _canonical_json_bytes(signature_payload)
    stored_signature = storage.put_bytes(signature_bytes, public_path=signature_public_path)

    manifest_payload = {
        "schema_version": 1,
        "kind": "private-skill-release-manifest",
        "release_id": release.id,
        "format_version": release.format_version,
        "sha256": stored_bundle.sha256,
        "skill": {
            "publisher": publisher,
            "name": skill_slug,
            "qualified_name": f"{publisher}/{skill_slug}",
            "display_name": snapshot.skill.display_name,
            "summary": snapshot.skill.summary,
            "version": version,
        },
        "bundle": {
            "path": bundle_public_path,
            "format": "tar.gz",
            "sha256": stored_bundle.sha256,
            "size": stored_bundle.size_bytes,
        },
        "provenance": {
            "path": provenance_public_path,
            "sha256": stored_provenance.sha256,
        },
        "signature": {
            "path": signature_public_path,
            "sha256": stored_signature.sha256,
        },
        "source_snapshot": {
            "content_ref": snapshot.draft.content_ref,
            "content_digest": snapshot.skill_version.content_digest,
            "metadata_digest": snapshot.skill_version.metadata_digest,
        },
    }
    manifest_bytes = _canonical_json_bytes(manifest_payload)
    stored_manifest = storage.put_bytes(manifest_bytes, public_path=manifest_public_path)

    bundle_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="bundle",
        storage_uri=stored_bundle.storage_uri,
        sha256=stored_bundle.sha256,
        size_bytes=stored_bundle.size_bytes,
    )
    manifest_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="manifest",
        storage_uri=stored_manifest.storage_uri,
        sha256=stored_manifest.sha256,
        size_bytes=stored_manifest.size_bytes,
    )
    provenance_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="provenance",
        storage_uri=stored_provenance.storage_uri,
        sha256=stored_provenance.sha256,
        size_bytes=stored_provenance.size_bytes,
    )
    signature_artifact = service.upsert_artifact(
        db,
        release_id=release.id,
        kind="signature",
        storage_uri=stored_signature.storage_uri,
        sha256=stored_signature.sha256,
        size_bytes=stored_signature.size_bytes,
    )
    service.mark_release_ready(
        db,
        release=release,
        manifest_artifact_id=manifest_artifact.id,
        bundle_artifact_id=bundle_artifact.id,
        signature_artifact_id=signature_artifact.id,
        provenance_artifact_id=provenance_artifact.id,
    )
    return release, service.get_artifacts_for_release(db, release.id)
