from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from server.modules.authoring.models import Skill, SkillVersion
from server.modules.shared.formatting import iso_format as _iso
from server.modules.shared.json import loads_json_object

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SEMVER_PATTERN = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


class SkillCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=SLUG_PATTERN)
    display_name: str = Field(min_length=1, max_length=200)
    summary: str = ""
    default_visibility_profile: str | None = Field(default=None, max_length=64)


class SkillVersionCreateRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64, pattern=SEMVER_PATTERN)
    content_mode: Literal["external_ref", "uploaded_bundle"] | None = None
    content_ref: str | None = Field(default=None, max_length=2000)
    content_upload_token: str | None = Field(default=None, max_length=500)
    metadata: dict = Field(default_factory=dict)


class SkillView(BaseModel):
    id: int
    namespace_id: int
    slug: str
    display_name: str
    summary: str
    status: str
    default_visibility_profile: str | None = None
    created_by_principal_id: int | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, skill: Skill) -> "SkillView":
        return cls(
            id=skill.id,
            namespace_id=skill.namespace_id,
            slug=skill.slug,
            display_name=skill.display_name,
            summary=skill.summary,
            status=skill.status,
            default_visibility_profile=skill.default_visibility_profile,
            created_by_principal_id=skill.created_by_principal_id,
            created_at=_iso(skill.created_at) or "",
            updated_at=_iso(skill.updated_at) or "",
        )


class SkillVersionView(BaseModel):
    id: int
    skill_id: int
    version: str
    content_digest: str
    metadata_digest: str
    sealed_manifest_json: str
    sealed_manifest: dict = Field(default_factory=dict)
    created_by_principal_id: int | None = None
    created_at: str

    @classmethod
    def from_model(cls, version: SkillVersion) -> "SkillVersionView":
        return cls(
            id=version.id,
            skill_id=version.skill_id,
            version=version.version,
            content_digest=version.content_digest,
            metadata_digest=version.metadata_digest,
            sealed_manifest_json=version.sealed_manifest_json,
            sealed_manifest=loads_json_object(version.sealed_manifest_json),
            created_by_principal_id=version.created_by_principal_id,
            created_at=_iso(version.created_at) or "",
        )
