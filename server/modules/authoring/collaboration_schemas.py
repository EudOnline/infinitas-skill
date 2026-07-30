from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from server.modules.authoring.models import SkillChangeSet
from server.modules.authoring.schemas import SEMVER_PATTERN
from server.modules.shared.formatting import iso_format
from server.modules.shared.json import loads_json_object

_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class ChangeSetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version_id: int | None = Field(ge=1)
    content_id: str = Field(min_length=8, max_length=64, pattern=r"^cnt_[A-Za-z0-9_-]+$")
    proposed_version: str = Field(min_length=1, max_length=64, pattern=SEMVER_PATTERN)


class ChangeSetAcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_latest_digest: str | None = Field(pattern=_DIGEST_PATTERN)


class ChangeSetView(BaseModel):
    id: str
    skill_id: int
    base_version_id: int | None
    candidate_content_id: str
    proposed_version: str
    state: Literal["open", "submitted", "accepted", "superseded", "rejected"]
    created_by_principal_id: int
    actor: dict = Field(default_factory=dict)
    created_at: str
    submitted_at: str | None
    decided_at: str | None

    @classmethod
    def from_model(cls, change_set: SkillChangeSet, *, content_public_id: str) -> "ChangeSetView":
        return cls(
            id=change_set.public_id,
            skill_id=change_set.skill_id,
            base_version_id=change_set.base_version_id,
            candidate_content_id=content_public_id,
            proposed_version=change_set.proposed_version,
            state=cast(
                Literal["open", "submitted", "accepted", "superseded", "rejected"],
                change_set.state,
            ),
            created_by_principal_id=change_set.created_by_principal_id,
            actor=loads_json_object(change_set.actor_metadata_json),
            created_at=iso_format(change_set.created_at) or "",
            submitted_at=iso_format(change_set.submitted_at),
            decided_at=iso_format(change_set.decided_at),
        )


class ChangeSetAcceptView(BaseModel):
    change_set: ChangeSetView
    version_id: int
    version: str
    content_digest: str


__all__ = [
    "ChangeSetAcceptRequest",
    "ChangeSetAcceptView",
    "ChangeSetCreateRequest",
    "ChangeSetView",
]
