"""Draft management service.

Handles draft CRUD operations, patching, and sealing.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.modules.authoring.models import SkillDraft
from server.modules.authoring.repository import (
    create_draft,
    create_skill_version,
    get_draft,
    update_draft,
)
from server.modules.authoring.schemas import SkillDraftCreateRequest, SkillDraftPatchRequest
from server.modules.authoring.services.base import (
    ConflictError,
    NotFoundError,
    load_metadata,
)
from server.modules.authoring.services.content_service import (
    build_sealed_manifest,
    calculate_content_digest,
    calculate_metadata_digest,
    resolve_content,
)
from server.modules.authoring.services.skill_service import (
    assert_namespace_owner,
    get_skill_or_404,
)
from server.modules.memory.service import record_lifecycle_memory_event_best_effort

# ── Draft CRUD ─────────────────────────────────────────────────────────────


def create_new_draft(
    db: Session,
    *,
    skill_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    payload: SkillDraftCreateRequest,
) -> SkillDraft:
    """Create a new draft.

    Args:
        db: Database session
        skill_id: Skill ID
        actor_principal_id: Principal creating the draft
        is_maintainer: Whether the actor is a maintainer
        payload: Draft creation request

    Returns:
        Created SkillDraft object

    Raises:
        NotFoundError: If skill not found
        ForbiddenError: If principal lacks access
        ConflictError: If content parameters are invalid
    """
    skill = get_skill_or_404(db, skill_id)
    assert_namespace_owner(
        db,
        skill=skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )

    resolved_mode, resolved_ref, content_artifact_id = resolve_content(
        db,
        content_mode=payload.content_mode,
        content_ref=payload.content_ref,
        content_upload_token=payload.content_upload_token,
    )

    draft = create_draft(
        db,
        skill_id=skill.id,
        created_by_principal_id=actor_principal_id,
        content_mode=resolved_mode,
        content_ref=resolved_ref,
        content_artifact_id=content_artifact_id,
        metadata_json=payload.metadata_json,
    )
    db.commit()
    db.refresh(draft)

    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.authoring.create_draft",
        aggregate_type="skill_draft",
        aggregate_id=str(draft.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "skill_id": str(skill.id),
            "skill_slug": skill.slug,
            "draft_id": str(draft.id),
        },
    )

    return draft


def get_draft_or_404(db: Session, draft_id: int) -> SkillDraft:
    """Get a draft by ID or raise 404.

    Args:
        db: Database session
        draft_id: Draft ID

    Returns:
        SkillDraft object

    Raises:
        NotFoundError: If draft not found
    """
    draft = get_draft(db, draft_id)
    if draft is None:
        raise NotFoundError("draft not found")
    return draft


def patch_existing_draft(
    db: Session,
    *,
    draft: SkillDraft,
    actor_principal_id: int,
    is_maintainer: bool = False,
    payload: SkillDraftPatchRequest,
) -> SkillDraft:
    """Patch an existing draft.

    Args:
        db: Database session
        draft: Draft to patch
        actor_principal_id: Principal patching the draft
        is_maintainer: Whether the actor is a maintainer
        payload: Draft patch request

    Returns:
        Updated SkillDraft object

    Raises:
        NotFoundError: If skill not found
        ForbiddenError: If principal lacks access
        ConflictError: If content parameters are invalid
    """
    skill = get_skill_or_404(db, draft.skill_id)
    assert_namespace_owner(
        db,
        skill=skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )

    updates: dict = {}

    # Handle content updates
    if payload.content_mode is not None or payload.content_ref is not None:
        resolved_mode, resolved_ref, content_artifact_id = resolve_content(
            db,
            content_mode=payload.content_mode,
            content_ref=payload.content_ref,
            content_upload_token=payload.content_upload_token,
        )
        updates["content_mode"] = resolved_mode
        updates["content_ref"] = resolved_ref
        updates["content_artifact_id"] = content_artifact_id

    # Handle metadata update
    if payload.metadata_json is not None:
        existing_metadata = load_metadata(draft.metadata_json)
        merged_metadata = {**existing_metadata, **load_metadata(payload.metadata_json)}
        updates["metadata_json"] = merged_metadata

    updated_draft = update_draft(db, draft, **updates)
    db.commit()
    db.refresh(updated_draft)

    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.authoring.patch_draft",
        aggregate_type="skill_draft",
        aggregate_id=str(updated_draft.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "skill_id": str(skill.id),
            "skill_slug": skill.slug,
            "draft_id": str(updated_draft.id),
        },
    )

    return updated_draft


# ── Draft Sealing ───────────────────────────────────────────────────────────


def seal_draft_as_version(
    db: Session,
    *,
    draft: SkillDraft,
    actor_principal_id: int,
    is_maintainer: bool = False,
    version: str,
    metadata: dict | None = None,
) -> SkillDraft:
    """Seal a draft into a version.

    Args:
        db: Database session
        draft: Draft to seal
        actor_principal_id: Principal sealing the draft
        is_maintainer: Whether the actor is a maintainer
        version: Version string
        metadata: Optional metadata override

    Returns:
        The sealed draft

    Raises:
        NotFoundError: If skill not found
        ForbiddenError: If principal lacks access
        ConflictError: If version already exists or content is not sealable
    """
    from server.modules.authoring.models import SkillVersion

    skill = get_skill_or_404(db, draft.skill_id)
    assert_namespace_owner(
        db,
        skill=skill,
        principal_id=actor_principal_id,
        is_maintainer=is_maintainer,
    )

    # Check for existing version
    existing_version = db.scalar(
        select(SkillVersion)
        .where(SkillVersion.skill_id == skill.id)
        .where(SkillVersion.version == version)
        .with_for_update()
    )
    if existing_version is not None:
        raise ConflictError("skill version already exists")

    # Calculate digests
    frozen_metadata = metadata if isinstance(metadata, dict) else load_metadata(draft.metadata_json)
    content_digest = calculate_content_digest(
        db,
        content_mode=draft.content_mode,
        content_ref=draft.content_ref,
        content_artifact_id=draft.content_artifact_id,
    )
    metadata_digest = calculate_metadata_digest(frozen_metadata)

    # Build and serialize manifest
    sealed_manifest_json = build_sealed_manifest(
        kind="skill_version_manifest",
        content_mode=draft.content_mode,
        content_ref=draft.content_ref,
        content_artifact_id=draft.content_artifact_id,
        metadata=frozen_metadata,
    )

    skill_version = create_skill_version(
        db,
        skill_id=skill.id,
        version=version,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        sealed_manifest_json=sealed_manifest_json,
        created_from_draft_id=draft.id,
        created_by_principal_id=actor_principal_id,
    )
    db.commit()
    db.refresh(skill_version)

    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.authoring.seal_draft",
        aggregate_type="skill_version",
        aggregate_id=str(skill_version.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "skill_id": str(skill.id),
            "skill_slug": skill.slug,
            "version": skill_version.version,
            "draft_id": str(draft.id),
        },
    )

    # Update draft to reference the version
    updated_draft = update_draft(db, draft, sealed_into_version_id=skill_version.id)
    db.commit()
    db.refresh(updated_draft)

    return updated_draft


__all__ = [
    "create_new_draft",
    "get_draft_or_404",
    "patch_existing_draft",
    "seal_draft_as_version",
]
