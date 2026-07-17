from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from infinitas_skill.install.distribution_core import DistributionError
from infinitas_skill.install.distribution_verification import verify_distribution_manifest
from server.modules.authoring.models import Skill, SkillVersion
from server.modules.exposure.models import Exposure
from server.modules.identity.models import Principal
from server.modules.release.models import Artifact, Release

_MAX_PROJECTION_BATCH_SIZE = 1000  # Maximum projections to process in one batch


@dataclass(frozen=True)
class DiscoveryProjection:
    exposure_id: int
    release_id: int
    audience_type: str
    listing_mode: str
    install_mode: str
    review_requirement: str
    exposure_state: str
    release_state: str
    publisher: str
    name: str
    qualified_name: str
    display_name: str
    summary: str
    version: str
    ready_at: datetime | None
    manifest_path: str
    bundle_path: str
    provenance_path: str
    signature_path: str
    bundle_sha256: str | None


def _artifact_paths(*, publisher: str, name: str, version: str) -> dict[str, str]:
    provenance_basename = f"{publisher}--{name}-{version}.json"
    return {
        "manifest_path": f"skills/{publisher}/{name}/{version}/manifest.json",
        "bundle_path": f"skills/{publisher}/{name}/{version}/skill.tar.gz",
        "provenance_path": f"provenance/{provenance_basename}",
        "signature_path": f"provenance/{provenance_basename}.ssig",
    }


def _artifact_exists(artifact_root: Path, relative_path: str) -> bool:
    if not isinstance(relative_path, str) or not relative_path.strip():
        return False
    root = Path(artifact_root).resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return candidate.is_file()


def projection_has_materialized_artifacts(
    entry: DiscoveryProjection,
    artifact_root: Path,
    repo_root: Path,
) -> bool:
    if not isinstance(entry.bundle_sha256, str) or not entry.bundle_sha256.strip():
        return False
    required_paths = (
        entry.manifest_path,
        entry.bundle_path,
        entry.provenance_path,
        entry.signature_path,
    )
    if not all(_artifact_exists(artifact_root, path) for path in required_paths):
        return False
    try:
        verified = verify_distribution_manifest(
            Path(artifact_root).resolve() / entry.manifest_path,
            root=artifact_root,
            attestation_root=repo_root,
        )
    except DistributionError:
        return False
    return bool(verified.get("verified"))


def _projection_query(
    *, audience_type: str | None, listing_mode: str | None, limit: int, offset: int
) -> Select[Any]:
    query = (
        select(
            Exposure.id.label("exposure_id"),
            Exposure.release_id.label("release_id"),
            Exposure.audience_type.label("audience_type"),
            Exposure.listing_mode.label("listing_mode"),
            Exposure.install_mode.label("install_mode"),
            Exposure.review_requirement.label("review_requirement"),
            Exposure.state.label("exposure_state"),
            Release.state.label("release_state"),
            Release.bundle_artifact_id.label("bundle_artifact_id"),
            Release.ready_at.label("ready_at"),
            Principal.slug.label("publisher"),
            Skill.slug.label("name"),
            Skill.display_name.label("display_name"),
            Skill.summary.label("summary"),
            SkillVersion.version.label("version"),
            SkillVersion.sealed_manifest_json.label("sealed_manifest_json"),
        )
        .join(Release, Release.id == Exposure.release_id)
        .join(SkillVersion, SkillVersion.id == Release.skill_version_id)
        .join(Skill, Skill.id == SkillVersion.skill_id)
        .join(Principal, Principal.id == Skill.namespace_id)
        .where(Release.state == "ready")
        .where(Exposure.state == "active")
        .where(Exposure.install_mode == "enabled")
    )
    if audience_type:
        query = query.where(Exposure.audience_type == audience_type)
    if listing_mode:
        query = query.where(Exposure.listing_mode == listing_mode)
    return (
        query.order_by(
            Principal.slug.asc(),
            Skill.slug.asc(),
            SkillVersion.version.desc(),
            Exposure.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )


def _bundle_sha_by_release(db: Session, rows: Sequence[Any]) -> dict[int, str]:
    artifact_ids = {
        int(row.bundle_artifact_id) for row in rows if row.bundle_artifact_id is not None
    }
    if not artifact_ids:
        return {}
    artifact_rows = db.execute(
        select(Artifact.id, Artifact.release_id, Artifact.sha256).where(
            Artifact.id.in_(artifact_ids)
        )
    ).all()
    return {int(row.release_id): row.sha256 for row in artifact_rows}


def _projection_from_row(row: Any, bundle_sha_by_release: dict[int, str]) -> DiscoveryProjection:
    publisher = str(row.publisher)
    name = str(row.name)
    version = str(row.version)
    paths = _artifact_paths(publisher=publisher, name=name, version=version)
    return DiscoveryProjection(
        exposure_id=int(row.exposure_id),
        release_id=int(row.release_id),
        audience_type=str(row.audience_type),
        listing_mode=str(row.listing_mode),
        install_mode=str(row.install_mode),
        review_requirement=str(row.review_requirement),
        exposure_state=str(row.exposure_state),
        release_state=str(row.release_state),
        publisher=publisher,
        name=name,
        qualified_name=f"{publisher}/{name}",
        display_name=str(row.display_name),
        summary=str(row.summary or ""),
        version=version,
        ready_at=row.ready_at,
        manifest_path=paths["manifest_path"],
        bundle_path=paths["bundle_path"],
        provenance_path=paths["provenance_path"],
        signature_path=paths["signature_path"],
        bundle_sha256=bundle_sha_by_release.get(int(row.release_id)),
    )


def build_release_projections(
    db: Session,
    *,
    audience_type: str | None = None,
    listing_mode: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[DiscoveryProjection]:
    """Build release projections with optional filtering and pagination.

    Args:
        db: Database session
        audience_type: Filter by audience type (e.g., 'public', 'grant', 'authenticated')
        listing_mode: Filter by listing mode (e.g., 'listed', 'unlisted')
        limit: Maximum number of projections to return (None for unlimited, capped at MAX)
        offset: Number of projections to skip (for pagination)
    Returns:
        List of DiscoveryProjection objects
    """
    # Apply safety cap on limit to prevent unbounded memory usage
    if limit is None:
        limit = _MAX_PROJECTION_BATCH_SIZE
    else:
        limit = min(limit, _MAX_PROJECTION_BATCH_SIZE)

    query = _projection_query(
        audience_type=audience_type,
        listing_mode=listing_mode,
        limit=limit,
        offset=offset,
    )
    rows = db.execute(query).all()
    bundle_sha_by_release = _bundle_sha_by_release(db, rows)
    return [_projection_from_row(row, bundle_sha_by_release) for row in rows]


def refresh_projection_snapshot(db: Session, artifact_root: Path) -> Path:
    artifact_root = Path(artifact_root).resolve()
    output = artifact_root / "catalog" / "private-registry-discovery.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
        "items": [asdict(item) for item in build_release_projections(db)],
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return output
