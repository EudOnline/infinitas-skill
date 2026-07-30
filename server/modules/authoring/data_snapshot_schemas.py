from __future__ import annotations

from typing import Literal, cast
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from server.modules.authoring.models import SkillDataSnapshot
from server.modules.shared.formatting import iso_format
from server.modules.shared.json import loads_json_object

_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"


class DataSnapshotRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_version_id: int = Field(ge=1)
    parent_snapshot_id: str | None = Field(default=None, pattern=r"^dsp_[A-Za-z0-9_-]+$")
    schema_version: int = Field(ge=1, le=1_000_000)
    encrypted_object_uri: str = Field(min_length=8, max_length=1000)
    ciphertext_sha256: str = Field(pattern=_DIGEST_PATTERN)
    ciphertext_size_bytes: int = Field(ge=1)
    manifest_digest: str = Field(pattern=_DIGEST_PATTERN)
    encryption: Literal["age"] = "age"

    @field_validator("encrypted_object_uri")
    @classmethod
    def validate_object_uri(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "openlist", "s3"}:
            raise ValueError("encrypted_object_uri must use https, openlist, or s3")
        if (
            not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "encrypted_object_uri must not contain credentials, query, or fragment"
            )
        if not parsed.path.endswith(".age"):
            raise ValueError("encrypted_object_uri must reference an age-encrypted object")
        return value


class DataSnapshotView(BaseModel):
    id: str
    skill_id: int
    skill_version_id: int
    parent_snapshot_id: str | None
    schema_version: int
    encrypted_object_uri: str
    ciphertext_sha256: str
    ciphertext_size_bytes: int
    manifest_digest: str
    encryption: Literal["age"]
    state: Literal["registered", "retired"]
    created_by_principal_id: int
    actor: dict = Field(default_factory=dict)
    created_at: str

    @classmethod
    def from_model(
        cls, snapshot: SkillDataSnapshot, *, parent_public_id: str | None
    ) -> "DataSnapshotView":
        return cls(
            id=snapshot.public_id,
            skill_id=snapshot.skill_id,
            skill_version_id=snapshot.skill_version_id,
            parent_snapshot_id=parent_public_id,
            schema_version=snapshot.schema_version,
            encrypted_object_uri=snapshot.encrypted_object_uri,
            ciphertext_sha256=snapshot.ciphertext_sha256,
            ciphertext_size_bytes=snapshot.ciphertext_size_bytes,
            manifest_digest=snapshot.manifest_digest,
            encryption=cast(Literal["age"], snapshot.encryption),
            state=cast(Literal["registered", "retired"], snapshot.state),
            created_by_principal_id=snapshot.created_by_principal_id,
            actor=loads_json_object(snapshot.actor_metadata_json),
            created_at=iso_format(snapshot.created_at) or "",
        )


__all__ = ["DataSnapshotRegisterRequest", "DataSnapshotView"]
