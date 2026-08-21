from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentInvitationCreateRequest(BaseModel):
    request_nonce: str = Field(pattern=r"^ainr_[A-Za-z0-9_-]{32}\.[A-Za-z0-9_-]{43}$")
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    display_name: str = Field(min_length=1, max_length=200)
    expires_in_minutes: int = Field(default=30, ge=5, le=1440)
    max_daily_publishes: int = Field(default=100, ge=1, le=100000)
    auto_public_publish: bool = True


class AgentInvitationCreatedView(BaseModel):
    public_id: str
    slug: str
    prompt: str
    invitation_token: str
    expires_at: str


class AgentEnrollmentSubmitRequest(BaseModel):
    status_verifier: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    api_key_verifier: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    fingerprint: str = Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$")
    runtime: dict[str, Any] = Field(default_factory=dict)


class AgentEnrollmentSubmitView(BaseModel):
    public_id: str
    state: str
    fingerprint: str
    expires_at: str


class AgentEnrollmentStatusView(BaseModel):
    public_id: str
    state: str
    slug: str
    fingerprint: str
    principal_slug: str | None = None
    principal_id: int | None = None
    reason: str | None = None


class AgentDecisionRequest(BaseModel):
    enrollment_public_id: str | None = Field(default=None, min_length=1, max_length=64)
    fingerprint: str | None = Field(default=None, min_length=16, max_length=16)
    note: str = Field(default="", max_length=2000)


class AgentCredentialRotateRequest(BaseModel):
    api_key_verifier: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    fingerprint: str = Field(min_length=16, max_length=16, pattern=r"^[0-9a-f]{16}$")


class AgentCredentialRotateView(BaseModel):
    ok: bool
    credential_id: int
    fingerprint: str


class AgentView(BaseModel):
    principal_id: int
    slug: str
    display_name: str
    state: str
    auto_public_publish: bool
    max_daily_publishes: int | None = None
