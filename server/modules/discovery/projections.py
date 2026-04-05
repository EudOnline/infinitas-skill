from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import Artifact, Exposure, Principal, Release, Skill, SkillVersion


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


def projection_has_materialized_artifacts(entry: DiscoveryProjection, artifact_root: Path) -> bool:
    if not isinstance(entry.bundle_sha256, str) or not entry.bundle_sha256.strip():
        return False
    return all(
        _artifact_exists(artifact_root, path)
        for path in (
            entry.manifest_path,
            entry.bundle_path,
            entry.provenance_path,
            entry.signature_path,
        )
    )


def build_release_projections(db: Session) -> list[DiscoveryProjection]:
    rows = db.execute(
        select(
            Exposure.id.label("exposure_id"),
            Exposure.release_id.label("release_id"),
            Exposure.audience_type.label("audience_type"),
            Exposure.listing_mode.label("listing_mode"),
            Exposure.install_mode.label("install_mode"),
            Exposure.review_requirement.label("review_requirement"),
            Exposure.state.label("exposure_state"),
            Release.state.label("release_state"),
            Release.ready_at.label("ready_at"),
            Principal.slug.label("publisher"),
            Skill.slug.label("name"),
            Skill.display_name.label("display_name"),
            Skill.summary.label("summary"),
            SkillVersion.version.label("version"),
        )
        .join(Release, Release.id == Exposure.release_id)
        .join(SkillVersion, SkillVersion.id == Release.skill_version_id)
        .join(Skill, Skill.id == SkillVersion.skill_id)
        .join(Principal, Principal.id == Skill.namespace_id)
        .where(Release.state == "ready")
        .where(Exposure.state == "active")
        .where(Exposure.install_mode == "enabled")
        .order_by(
            Principal.slug.asc(),
            Skill.slug.asc(),
            SkillVersion.version.desc(),
            Exposure.id.desc(),
        )
    ).all()

    release_ids = {int(row.release_id) for row in rows}
    bundle_sha_by_release: dict[int, str] = {}
    if release_ids:
        artifact_rows = db.execute(
            select(Artifact.release_id, Artifact.kind, Artifact.sha256).where(
                Artifact.release_id.in_(release_ids)
            )
        ).all()
        for artifact_row in artifact_rows:
            if artifact_row.kind == "bundle":
                bundle_sha_by_release[int(artifact_row.release_id)] = artifact_row.sha256

    projections: list[DiscoveryProjection] = []
    for row in rows:
        publisher = str(row.publisher)
        name = str(row.name)
        version = str(row.version)
        paths = _artifact_paths(publisher=publisher, name=name, version=version)
        projections.append(
            DiscoveryProjection(
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
        )
    return projections


def refresh_projection_snapshot(db: Session, artifact_root: Path) -> Path:
    artifact_root = Path(artifact_root).resolve()
    output = artifact_root / "catalog" / "private-registry-discovery.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "items": [asdict(item) for item in build_release_projections(db)],
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return output
