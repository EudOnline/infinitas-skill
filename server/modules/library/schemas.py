from __future__ import annotations

from pydantic import BaseModel, Field


class LibraryVisibilityView(BaseModel):
    audience_type: str | None = None
    listing_mode: str | None = None
    install_mode: str | None = None
    state: str | None = None


class LibraryCurrentReleaseView(BaseModel):
    release_id: int
    version: str | None = None
    state: str
    ready_at: str | None = None


class LibraryObjectView(BaseModel):
    id: int
    kind: str
    slug: str
    name: str
    display_name: str
    summary: str
    updated_at: str
    current_release: LibraryCurrentReleaseView | None = None
    version: str | None = None
    current_visibility: LibraryVisibilityView
    token_count: int
    share_link_count: int
    detail_href: str


class LibraryObjectTypeDetailsView(BaseModel):
    kind: str
    default_visibility_profile: str | None = None


class LibraryReleaseView(BaseModel):
    release_id: int
    version: str | None = None
    state: str
    created_at: str
    ready_at: str | None = None
    visibility: LibraryVisibilityView


class LibraryObjectDetailView(BaseModel):
    object: LibraryObjectView
    details: LibraryObjectTypeDetailsView
    releases: list[LibraryReleaseView] = Field(default_factory=list)


class LibraryObjectListView(BaseModel):
    items: list[LibraryObjectView] = Field(default_factory=list)
    total: int = 0
    skip: int = 0
    limit: int = 20
    has_more: bool = False


class LibraryReleaseListView(BaseModel):
    items: list[LibraryReleaseView] = Field(default_factory=list)
    total: int = 0
    skip: int = 0
    limit: int = 20
    has_more: bool = False
