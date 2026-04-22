from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from infinitas_skill.install.distribution import DistributionError, verify_distribution_manifest
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
    kind: str
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
    supported_memory_modes: list[str] | None = None
    default_memory_mode: str | None = None


def _memory_metadata_from_manifest(raw: str | None) -> tuple[list[str] | None, str | None]:
    if not raw:
        return None, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None, None
    if not isinstance(payload, dict):
        return None, None
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return None, None
    supported = [
        str(item).strip()
        for item in (metadata.get("supported_memory_modes") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    default_mode = metadata.get("default_memory_mode")
    if not isinstance(default_mode, str) or not default_mode.strip():
        default_mode = None
    return (supported or None), default_mode


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
            Release.bundle_artifact_id.label("bundle_artifact_id"),
            Release.object_kind.label("kind"),
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
        .order_by(
            Principal.slug.asc(),
            Skill.slug.asc(),
            SkillVersion.version.desc(),
            Exposure.id.desc(),
        )
    ).all()

    bundle_artifact_ids = {
        int(row.bundle_artifact_id)
        for row in rows
        if row.bundle_artifact_id is not None
    }
    bundle_sha_by_release: dict[int, str] = {}
    if bundle_artifact_ids:
        artifact_rows = db.execute(
            select(Artifact.id, Artifact.release_id, Artifact.sha256).where(
                Artifact.id.in_(bundle_artifact_ids)
            )
        ).all()
        for artifact_row in artifact_rows:
            bundle_sha_by_release[int(artifact_row.release_id)] = artifact_row.sha256

    projections: list[DiscoveryProjection] = []
    for row in rows:
        publisher = str(row.publisher)
        name = str(row.name)
        version = str(row.version)
        paths = _artifact_paths(publisher=publisher, name=name, version=version)
        supported_memory_modes, default_memory_mode = _memory_metadata_from_manifest(
            row.sealed_manifest_json
        )
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
                kind=str(row.kind or "skill"),
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
                supported_memory_modes=supported_memory_modes,
                default_memory_mode=default_memory_mode,
            )
        )
    return projections


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
