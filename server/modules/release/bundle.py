"""Bundle construction for the release materializer.

Handles in-memory tar.gz bundle creation, artifact path resolution,
and uploaded-bundle loading from the database and filesystem.
"""
from __future__ import annotations

import gzip
import io
import json
import tarfile
from pathlib import Path

from sqlalchemy.orm import Session

from infinitas_skill.install.distribution import inspect_distribution_bundle
from server.modules.release.models import Artifact


def canonical_json_bytes(payload: dict) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def bundle_bytes(*, skill_slug: str, content_ref: str, metadata: dict) -> tuple[bytes, int]:
    buffer = io.BytesIO()
    file_count = 0
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gzip_file:
        with tarfile.open(fileobj=gzip_file, mode="w", format=tarfile.PAX_FORMAT) as archive:
            entries = {
                f"{skill_slug}/snapshot/content-ref.txt": (
                    content_ref.rstrip("\n") + "\n"
                ).encode("utf-8"),
                f"{skill_slug}/snapshot/metadata.json": canonical_json_bytes(metadata),
            }
            file_count = len(entries)
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
    return buffer.getvalue(), file_count


def artifact_object_path(*, artifact_root: Path, storage_uri: str) -> Path:
    root = Path(artifact_root).resolve()
    candidate = (root / str(storage_uri or "")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"artifact storage_uri escapes artifact root: {storage_uri!r}") from exc
    return candidate


def _bundle_root_dir(bundle_path: Path) -> str:
    with tarfile.open(bundle_path, mode="r:gz") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.parts:
                return str(member_path.parts[0])
    raise RuntimeError(f"bundle has no archive members: {bundle_path}")


def uploaded_bundle_data(
    db: Session,
    *,
    artifact_root: Path,
    content_artifact_id: int | None,
) -> tuple[bytes, int, str]:
    if content_artifact_id is None:
        raise RuntimeError("uploaded_bundle draft is missing content_artifact_id")
    artifact = db.get(Artifact, int(content_artifact_id))
    if artifact is None:
        raise RuntimeError(f"uploaded bundle artifact {content_artifact_id} not found")
    source_path = artifact_object_path(
        artifact_root=artifact_root, storage_uri=artifact.storage_uri
    )
    if not source_path.is_file():
        raise RuntimeError(f"uploaded bundle artifact payload missing: {source_path}")
    raw = source_path.read_bytes()
    bundle_metadata = inspect_distribution_bundle(source_path, expected_root=None)
    file_manifest = bundle_metadata.get("file_manifest") or []
    return raw, len(file_manifest), _bundle_root_dir(source_path)


def content_ref_commit(content_ref: str, fallback: str) -> str:
    ref = str(content_ref or "")
    if "#" in ref:
        candidate = ref.rsplit("#", 1)[-1].strip()
        if candidate:
            return candidate
    return fallback
