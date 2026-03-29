from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.modules.authoring.models import Skill, SkillDraft, SkillVersion


def get_skill(db: Session, skill_id: int) -> Skill | None:
    return db.get(Skill, skill_id)


def get_skill_by_namespace_and_slug(db: Session, *, namespace_id: int, slug: str) -> Skill | None:
    return db.scalar(
        select(Skill)
        .where(Skill.namespace_id == namespace_id)
        .where(Skill.slug == slug)
    )


def create_skill(
    db: Session,
    *,
    namespace_id: int,
    slug: str,
    display_name: str,
    summary: str,
    default_visibility_profile: str | None,
    created_by_principal_id: int | None,
) -> Skill:
    skill = Skill(
        namespace_id=namespace_id,
        slug=slug,
        display_name=display_name,
        summary=summary,
        status="active",
        default_visibility_profile=default_visibility_profile,
        created_by_principal_id=created_by_principal_id,
    )
    db.add(skill)
    db.flush()
    return skill


def get_draft(db: Session, draft_id: int) -> SkillDraft | None:
    return db.get(SkillDraft, draft_id)


def create_draft(
    db: Session,
    *,
    skill_id: int,
    base_version_id: int | None,
    content_ref: str,
    metadata_json: str,
    updated_by_principal_id: int | None,
) -> SkillDraft:
    draft = SkillDraft(
        skill_id=skill_id,
        base_version_id=base_version_id,
        state="open",
        content_ref=content_ref,
        metadata_json=metadata_json,
        updated_by_principal_id=updated_by_principal_id,
    )
    db.add(draft)
    db.flush()
    return draft


def get_skill_version(db: Session, skill_version_id: int) -> SkillVersion | None:
    return db.get(SkillVersion, skill_version_id)


def get_skill_version_by_skill_and_version(db: Session, *, skill_id: int, version: str) -> SkillVersion | None:
    return db.scalar(
        select(SkillVersion)
        .where(SkillVersion.skill_id == skill_id)
        .where(SkillVersion.version == version)
    )


def create_skill_version(
    db: Session,
    *,
    skill_id: int,
    version: str,
    content_digest: str,
    metadata_digest: str,
    created_from_draft_id: int | None,
    created_by_principal_id: int | None,
) -> SkillVersion:
    skill_version = SkillVersion(
        skill_id=skill_id,
        version=version,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        created_from_draft_id=created_from_draft_id,
        created_by_principal_id=created_by_principal_id,
    )
    db.add(skill_version)
    db.flush()
    return skill_version
