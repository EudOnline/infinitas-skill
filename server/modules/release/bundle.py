"""Validated Hosted bundle loading for the release materializer."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from sqlalchemy.orm import Session

from infinitas_skill.install.distribution_core import inspect_distribution_bundle
from server.modules.authoring.models import SkillContent


def canonical_json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


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


def skill_content_bundle_data(
    db: Session,
    *,
    artifact_root: Path,
    content_id: int,
) -> tuple[bytes, int, str]:
    content = db.get(SkillContent, content_id)
    if content is None:
        raise RuntimeError(f"skill content {content_id} not found")
    source_path = artifact_object_path(artifact_root=artifact_root, storage_uri=content.storage_uri)
    if not source_path.is_file():
        raise RuntimeError(f"skill content payload missing: {source_path}")
    raw = source_path.read_bytes()
    bundle_metadata = inspect_distribution_bundle(source_path, expected_root=None)
    file_manifest = bundle_metadata.get("file_manifest") or []
    return raw, len(file_manifest), _bundle_root_dir(source_path)
