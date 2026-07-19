from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer


class ProfileIdentityView(BaseModel):
    credential_id: int
    credential_type: str
    principal_id: int | None = None
    principal_slug: str | None = None
    principal_kind: str | None = None
    principal_display_name: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None


class AccessibleSkillView(BaseModel):
    id: int
    slug: str
    display_name: str
    kind: str


class OperationHistoryView(BaseModel):
    id: int
    aggregate_type: str
    aggregate_id: str
    event_type: str
    actor_ref: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str | None = None


class CredentialPolicyView(BaseModel):
    model_config = ConfigDict(extra="allow")

    max_daily_publishes: int | None = None
    readonly: bool | None = None
    allowed_object_kinds: list[str] | None = None

    @model_serializer(mode="wrap")
    def serialize_without_unset_policy_fields(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        serialized = handler(self)
        return {key: value for key, value in serialized.items() if value is not None}


class CredentialProfileView(BaseModel):
    identity: ProfileIdentityView
    accessible_skills: list[AccessibleSkillView] = Field(default_factory=list)
    operation_history: list[OperationHistoryView] = Field(default_factory=list)
    policy: CredentialPolicyView | None = None


class CredentialPolicyUpdateView(BaseModel):
    status: Literal["updated"]
    policy: CredentialPolicyView | None = None
