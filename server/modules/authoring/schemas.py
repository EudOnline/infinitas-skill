from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel, Field

from server.modules.authoring.models import Skill, SkillDraft, SkillVersion


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _load_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
SEMVER_PATTERN = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)


class SkillCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=SLUG_PATTERN)
    display_name: str = Field(min_length=1, max_length=200)
    summary: str = ""
    default_visibility_profile: str | None = None


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


class SkillDraftCreateRequest(BaseModel):
    base_version_id: int | None = None
    content_ref: str = ""
    metadata: dict = Field(default_factory=dict)


class SkillDraftPatchRequest(BaseModel):
    content_ref: str | None = None
    metadata: dict | None = None


class SkillDraftView(BaseModel):
    id: int
    skill_id: int
    base_version_id: int | None = None
    state: str
    content_ref: str
    metadata: dict = Field(default_factory=dict)
    updated_by_principal_id: int | None = None
    updated_at: str

    @classmethod
    def from_model(cls, draft: SkillDraft) -> "SkillDraftView":
        return cls(
            id=draft.id,
            skill_id=draft.skill_id,
            base_version_id=draft.base_version_id,
            state=draft.state,
            content_ref=draft.content_ref,
            metadata=_load_metadata(draft.metadata_json),
            updated_by_principal_id=draft.updated_by_principal_id,
            updated_at=_iso(draft.updated_at) or "",
        )


class SkillDraftSealRequest(BaseModel):
    version: str = Field(min_length=1, max_length=64, pattern=SEMVER_PATTERN)


class SkillVersionView(BaseModel):
    id: int
    skill_id: int
    version: str
    content_digest: str
    metadata_digest: str
    created_from_draft_id: int | None = None
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
            created_from_draft_id=version.created_from_draft_id,
            created_by_principal_id=version.created_by_principal_id,
            created_at=_iso(version.created_at) or "",
        )


class SkillDraftSealResponse(BaseModel):
    version: str
    draft: SkillDraftView
    skill_version: SkillVersionView
