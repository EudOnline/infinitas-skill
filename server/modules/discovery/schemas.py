from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from server.modules.discovery.projections import DiscoveryProjection


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


class CatalogEntryView(BaseModel):
    exposure_id: int
    release_id: int
    audience_type: str
    listing_mode: str
    name: str
    qualified_name: str
    publisher: str
    version: str
    display_name: str
    summary: str = ""
    ready_at: str | None = None
    manifest_path: str
    bundle_path: str
    provenance_path: str
    signature_path: str
    bundle_sha256: str | None = None

    @classmethod
    def from_projection(cls, entry: DiscoveryProjection) -> "CatalogEntryView":
        return cls(
            exposure_id=entry.exposure_id,
            release_id=entry.release_id,
            audience_type=entry.audience_type,
            listing_mode=entry.listing_mode,
            name=entry.name,
            qualified_name=entry.qualified_name,
            publisher=entry.publisher,
            version=entry.version,
            display_name=entry.display_name,
            summary=entry.summary,
            ready_at=_iso(entry.ready_at),
            manifest_path=entry.manifest_path,
            bundle_path=entry.bundle_path,
            provenance_path=entry.provenance_path,
            signature_path=entry.signature_path,
            bundle_sha256=entry.bundle_sha256,
        )


class CatalogListView(BaseModel):
    items: list[CatalogEntryView] = Field(default_factory=list)
    total: int = 0


class InstallResolutionView(BaseModel):
    exposure_id: int
    release_id: int
    audience_type: str
    name: str
    qualified_name: str
    publisher: str
    version: str
    display_name: str
    summary: str = ""
    ready_at: str | None = None
    manifest_path: str
    bundle_path: str
    provenance_path: str
    signature_path: str
    bundle_sha256: str | None = None
    manifest_download_path: str
    bundle_download_path: str
    provenance_download_path: str
    signature_download_path: str
    manifest_url: str
    bundle_url: str
    provenance_url: str
    signature_url: str


class ProjectionArtifactPaths(BaseModel):
    manifest_download_path: str
    bundle_download_path: str
    provenance_download_path: str
    signature_download_path: str
    manifest_url: str
    bundle_url: str
    provenance_url: str
    signature_url: str
