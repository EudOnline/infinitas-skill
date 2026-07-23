from __future__ import annotations

from typing_extensions import TypedDict


class VisibilityReadModel(TypedDict):
    audience_type: str | None
    listing_mode: str | None
    install_mode: str | None
    state: str | None


class CurrentReleaseReadModel(TypedDict):
    release_id: int
    version: str | None
    state: str
    ready_at: str | None


class LibraryObjectReadModel(TypedDict):
    id: int
    kind: str
    slug: str
    name: str
    display_name: str
    summary: str
    updated_at: str
    current_release: CurrentReleaseReadModel | None
    version: str | None
    current_visibility: VisibilityReadModel
    token_count: int
    share_link_count: int
    detail_href: str


class LibraryObjectTypeDetailsReadModel(TypedDict):
    kind: str
    default_visibility_profile: str | None


class LibraryReleaseReadModel(TypedDict):
    release_id: int
    version: str | None
    state: str
    created_at: str
    ready_at: str
    visibility: VisibilityReadModel
    content_digest: str
    metadata_digest: str


class ArtifactReadModel(TypedDict):
    id: int
    kind: str
    sha256: str
    size_bytes: str
    storage_uri: str


class VisibilityActionReadModel(TypedDict):
    can_activate: bool
    can_revoke: bool
    can_patch: bool
    activation_block_reason: str


class ReleaseVisibilityReadModel(TypedDict):
    id: int
    visibility: str
    listing_mode: str
    listing_mode_raw: str
    install_mode: str
    install_mode_raw: str
    state: str
    state_raw: str
    share_count: int
    token_count: int
    review_case_id: int | None
    review_case_mode_raw: str
    review_case_state_raw: str
    can_review: bool
    can_activate: bool
    can_revoke: bool
    can_patch: bool
    activation_block_reason: str


class LibraryObjectDetailReadModel(TypedDict):
    object: LibraryObjectReadModel
    details: LibraryObjectTypeDetailsReadModel
    releases: list[LibraryReleaseReadModel]
