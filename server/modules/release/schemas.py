from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, Field

from server.modules.release.models import Artifact, Release


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


class ReleaseView(BaseModel):
    id: int
    skill_version_id: int
    state: str
    format_version: str
    manifest_artifact_id: int | None = None
    bundle_artifact_id: int | None = None
    signature_artifact_id: int | None = None
    provenance_artifact_id: int | None = None
    created_by_principal_id: int | None = None
    created_at: str
    ready_at: str | None = None
    platform_compatibility: dict = {}

    @classmethod
    def from_model(cls, release: Release) -> "ReleaseView":
        try:
            platform_compatibility = json.loads(release.platform_compatibility_json or "{}")
        except json.JSONDecodeError:
            platform_compatibility = {}
        return cls(
            id=release.id,
            skill_version_id=release.skill_version_id,
            state=release.state,
            format_version=release.format_version,
            manifest_artifact_id=release.manifest_artifact_id,
            bundle_artifact_id=release.bundle_artifact_id,
            signature_artifact_id=release.signature_artifact_id,
            provenance_artifact_id=release.provenance_artifact_id,
            created_by_principal_id=release.created_by_principal_id,
            created_at=_iso(release.created_at) or "",
            ready_at=_iso(release.ready_at),
            platform_compatibility=platform_compatibility,
        )


class ArtifactView(BaseModel):
    id: int
    release_id: int
    kind: str
    storage_uri: str
    sha256: str
    size_bytes: int
    created_at: str

    @classmethod
    def from_model(cls, artifact: Artifact) -> "ArtifactView":
        return cls(
            id=artifact.id,
            release_id=artifact.release_id,
            kind=artifact.kind,
            storage_uri=artifact.storage_uri,
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            created_at=_iso(artifact.created_at) or "",
        )


class ArtifactListView(BaseModel):
    items: list[ArtifactView] = Field(default_factory=list)
    total: int = 0
