"""Version management service.

Handles skill version creation and snapshot management.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.modules.authoring.models import SkillVersion
from server.modules.authoring.repository import (
    create_skill_version,
)
from server.modules.authoring.services.base import (
    ConflictError,
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

# ── Version Creation ───────────────────────────────────────────────────────


def create_version_snapshot(
    db: Session,
    *,
    skill_id: int,
    actor_principal_id: int,
    is_maintainer: bool = False,
    version: str,
    content_mode: str | None = None,
    content_ref: str | None = None,
    content_upload_token: str | None = None,
    metadata: dict | None = None,
) -> SkillVersion:
    """Create a skill version snapshot.

    Args:
        db: Database session
        skill_id: Skill ID
        actor_principal_id: Principal creating the version
        is_maintainer: Whether the actor is a maintainer
        version: Version string
        content_mode: Content mode (external_ref or uploaded_bundle)
        content_ref: Content reference (git+ URL or external ref)
        content_upload_token: Upload token for bundle uploads
        metadata: Optional metadata dictionary

    Returns:
        Created SkillVersion object

    Raises:
        NotFoundError: If skill not found
        ForbiddenError: If principal lacks access
        ConflictError: If version already exists or content parameters are invalid
    """
    skill = get_skill_or_404(db, skill_id)
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

    # Resolve content
    resolved_mode, resolved_ref, content_artifact_id = resolve_content(
        db,
        content_mode=content_mode,
        content_ref=content_ref,
        content_upload_token=content_upload_token,
    )

    # Calculate digests
    frozen_metadata = metadata if isinstance(metadata, dict) else {}
    content_digest = calculate_content_digest(
        db,
        content_mode=resolved_mode,
        content_ref=resolved_ref,
        content_artifact_id=content_artifact_id,
    )
    metadata_digest = calculate_metadata_digest(frozen_metadata)

    # Build and serialize manifest
    sealed_manifest_json = build_sealed_manifest(
        kind="skill_version_manifest",
        content_mode=resolved_mode,
        content_ref=resolved_ref,
        content_artifact_id=content_artifact_id,
        metadata=frozen_metadata,
    )

    skill_version = create_skill_version(
        db,
        skill_id=skill.id,
        version=version,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        sealed_manifest_json=sealed_manifest_json,
        created_from_draft_id=None,
        created_by_principal_id=actor_principal_id,
    )
    db.commit()
    db.refresh(skill_version)

    record_lifecycle_memory_event_best_effort(
        db,
        lifecycle_event="task.authoring.create_version",
        aggregate_type="skill_version",
        aggregate_id=str(skill_version.id),
        actor_ref=f"principal:{actor_principal_id}",
        payload={
            "skill_id": str(skill.id),
            "skill_slug": skill.slug,
            "version": skill_version.version,
            "skill_version_id": str(skill_version.id),
        },
    )

    return skill_version


__all__ = [
    "create_version_snapshot",
]
