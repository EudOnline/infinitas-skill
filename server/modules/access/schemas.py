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


class ProductTokenView(BaseModel):
    id: int
    name: str
    type: str
    scope_type: str
    scope_id: int
    issued_for: str | None = None
    state: str
    scopes: list[str] = Field(default_factory=list)
    expires_at: str | None = None
    created_at: str | None = None
    last_used_at: str | None = None


class ProductTokenCreateView(BaseModel):
    raw_token: str
    token: ProductTokenView


class ProductTokenListView(BaseModel):
    items: list[ProductTokenView] = Field(default_factory=list)
    total: int = 0


class ShareLinkView(BaseModel):
    id: int
    grant_id: int
    credential_id: int | None = None
    release_id: int
    name: str
    slug: str
    has_password: bool
    expires_at: str | None = None
    max_uses: int | None = None
    used_count: int
    state: str
    created_at: str | None = None
    install_path: str | None = None
    install_url: str | None = None
    resolve_path: str | None = None
    resolve_url: str | None = None
    resolve_secret: str | None = None
    access_token: str | None = None


class ShareLinkListView(BaseModel):
    items: list[ShareLinkView] = Field(default_factory=list)
    total: int = 0
