from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from infinitas_skill.install.distribution import DistributionError, verify_distribution_manifest
from server.models import Artifact, Exposure, Principal, Release, Skill, SkillVersion

# Cache configuration
_PROJECTION_CACHE_MAXSIZE = 128
_PROJECTION_CACHE_TTL = 300  # 5 minutes
_MAX_PROJECTION_BATCH_SIZE = 1000  # Maximum projections to process in one batch


# In-memory cache with timestamp tracking
_projection_cache: dict[str, CacheEntry] = {}
_cache_access_order: list[str] = []  # For LRU eviction


def _get_cache_key(
    audience_type: str | None = None,
    listing_mode: str | None = None,
    limit: int | None = None,
) -> str:
    """Generate cache key for projection queries."""
    parts = ["projections"]
    if audience_type:
        parts.append(f"audience:{audience_type}")
    if listing_mode:
        parts.append(f"listing:{listing_mode}")
    if limit:
        parts.append(f"limit:{limit}")
    return ":".join(parts)


def _get_cached_projections(cache_key: str) -> list[DiscoveryProjection] | None:
    """Get projections from cache if valid."""
    entry = _projection_cache.get(cache_key)
    if entry is not None and _is_cache_entry_valid(entry):
        # Update access order for LRU
        if cache_key in _cache_access_order:
            _cache_access_order.remove(cache_key)
        _cache_access_order.append(cache_key)
        return entry.projections
    return None


def _set_cached_projections(cache_key: str, projections: list[DiscoveryProjection]) -> None:
    """Store projections in cache with LRU eviction."""
    # Evict oldest entries if cache is full
    while len(_projection_cache) >= _PROJECTION_CACHE_MAXSIZE and _cache_access_order:
        oldest_key = _cache_access_order.pop(0)
        _projection_cache.pop(oldest_key, None)

    _projection_cache[cache_key] = CacheEntry(
        projections=projections,
        timestamp=time.time(),
    )
    if cache_key in _cache_access_order:
        _cache_access_order.remove(cache_key)
    _cache_access_order.append(cache_key)


def cleanup_expired_cache_entries(ttl: int = _PROJECTION_CACHE_TTL) -> int:
    """Remove expired entries from the projection cache.

    Returns:
        Number of entries removed.
    """
    now = time.time()
    expired_keys = [key for key, entry in _projection_cache.items() if now - entry.timestamp >= ttl]
    for key in expired_keys:
        _projection_cache.pop(key, None)
        if key in _cache_access_order:
            _cache_access_order.remove(key)
    return len(expired_keys)


@dataclass(frozen=True)
class CacheEntry:
    """Cache entry with timestamp for TTL expiration."""

    projections: list[DiscoveryProjection]
    timestamp: float


def _is_cache_entry_valid(entry: CacheEntry | None, ttl: int = _PROJECTION_CACHE_TTL) -> bool:
    """Check if cache entry is still valid based on TTL."""
    if entry is None:
        return False
    return time.time() - entry.timestamp < ttl


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


def build_release_projections(
    db: Session,
    *,
    audience_type: str | None = None,
    listing_mode: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    use_cache: bool = True,
) -> list[DiscoveryProjection]:
    """Build release projections with optional filtering and pagination.

    Args:
        db: Database session
        audience_type: Filter by audience type (e.g., 'public', 'grant', 'authenticated')
        listing_mode: Filter by listing mode (e.g., 'listed', 'unlisted')
        limit: Maximum number of projections to return (None for unlimited, capped at MAX)
        offset: Number of projections to skip (for pagination)
        use_cache: Whether to use in-memory cache for results

    Returns:
        List of DiscoveryProjection objects
    """
    # Apply safety cap on limit to prevent unbounded memory usage
    if limit is None:
        limit = _MAX_PROJECTION_BATCH_SIZE
    else:
        limit = min(limit, _MAX_PROJECTION_BATCH_SIZE)

    # Check cache first if enabled
    if use_cache:
        cache_key = _get_cache_key(
            audience_type=audience_type, listing_mode=listing_mode, limit=limit
        )
        cached = _get_cached_projections(cache_key)
        if cached is not None:
            return cached[offset : offset + limit]

    # Build query with filters
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

    # Apply optional filters
    if audience_type:
        query = query.where(Exposure.audience_type == audience_type)
    if listing_mode:
        query = query.where(Exposure.listing_mode == listing_mode)

    query = query.order_by(
        Principal.slug.asc(),
        Skill.slug.asc(),
        SkillVersion.version.desc(),
        Exposure.id.desc(),
    )

    # Apply pagination at database level
    query = query.offset(offset).limit(limit)

    rows = db.execute(query).all()

    bundle_artifact_ids = {
        int(row.bundle_artifact_id) for row in rows if row.bundle_artifact_id is not None
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

    # Store in cache if enabled
    if use_cache:
        cache_key = _get_cache_key(
            audience_type=audience_type, listing_mode=listing_mode, limit=limit
        )
        _set_cached_projections(cache_key, projections)

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
