"""Authoring services module.

Provides a clean separation of concerns for authoring operations.
This module re-exports all services for backward compatibility.
"""
from __future__ import annotations

# Import all exception classes and utilities from base
from server.modules.authoring.services.base import (
    _CONTENT_MODES,
    AuthoringError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    canonical_manifest_json,
    canonical_metadata_json,
    is_sealable_content_ref,
    is_valid_content_mode,
    load_metadata,
    sha256_prefixed,
)

# Import content service
from server.modules.authoring.services.content_service import (
    _parse_artifact_token,
    _resolve_uploaded_content_artifact,
    build_sealed_manifest,
    build_version_manifest,
    calculate_content_digest,
    calculate_metadata_digest,
    resolve_content,
)

# Import draft service
from server.modules.authoring.services.draft_service import (
    create_new_draft,
    get_draft_or_404,
    patch_existing_draft,
    seal_draft_as_version,
)

# Import skill service
from server.modules.authoring.services.skill_service import (
    _check_team_access,
    assert_namespace_access,
    assert_namespace_owner,
    create_new_skill,
    get_skill_or_404,
)

# Import version service
from server.modules.authoring.services.version_service import (
    create_version_snapshot,
)

# Backward compatibility aliases - map old function names to new service functions
create_skill = create_new_skill
create_draft = create_new_draft
patch_draft = patch_existing_draft
seal_draft = seal_draft_as_version
create_skill_version_snapshot = create_version_snapshot


__all__ = [
    # Exceptions
    "AuthoringError",
    "NotFoundError",
    "ConflictError",
    "ForbiddenError",
    # Utilities
    "canonical_metadata_json",
    "load_metadata",
    "sha256_prefixed",
    "canonical_manifest_json",
    "is_sealable_content_ref",
    "is_valid_content_mode",
    "_CONTENT_MODES",
    # Content service
    "resolve_content",
    "calculate_content_digest",
    "calculate_metadata_digest",
    "build_version_manifest",
    "build_sealed_manifest",
    "_parse_artifact_token",
    "_resolve_uploaded_content_artifact",
    # Skill service
    "get_skill_or_404",
    "create_new_skill",
    "assert_namespace_access",
    "assert_namespace_owner",
    "_check_team_access",
    # Draft service
    "create_new_draft",
    "get_draft_or_404",
    "patch_existing_draft",
    "seal_draft_as_version",
    # Version service
    "create_version_snapshot",
    # Backward compatibility
    "create_skill",
    "create_draft",
    "patch_draft",
    "seal_draft",
    "create_skill_version_snapshot",
]
