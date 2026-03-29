from __future__ import annotations

from pydantic import BaseModel, Field


class AccessIdentityView(BaseModel):
    credential_id: int
    credential_type: str
    principal_id: int | None = None
    principal_kind: str | None = None
    principal_slug: str | None = None
    user_id: int | None = None
    username: str | None = None
    scopes: list[str] = Field(default_factory=list)


class ReleaseAccessCheckView(BaseModel):
    ok: bool
    release_id: int
    credential_type: str
    principal_id: int | None = None
    scope_granted: bool
