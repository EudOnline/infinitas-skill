from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from server.model_base import utcnow
from server.modules.authoring.models import Skill, SkillContent, SkillVersion


def get_skill(db: Session, skill_id: int) -> Skill | None:
    return db.get(Skill, skill_id)


def get_skill_content_by_public_id(db: Session, public_id: str) -> SkillContent | None:
    return db.scalar(select(SkillContent).where(SkillContent.public_id == public_id))


def create_skill_content(
    db: Session,
    *,
    public_id: str,
    skill_id: int,
    storage_uri: str,
    sha256: str,
    size_bytes: int,
    declared_version: str,
    created_by_principal_id: int,
) -> SkillContent:
    content = SkillContent(
        public_id=public_id,
        skill_id=skill_id,
        storage_uri=storage_uri,
        sha256=sha256,
        size_bytes=size_bytes,
        declared_version=declared_version,
        state="validated",
        created_by_principal_id=created_by_principal_id,
    )
    db.add(content)
    db.flush()
    return content


def get_skill_by_namespace_and_slug(db: Session, *, namespace_id: int, slug: str) -> Skill | None:
    return db.scalar(
        select(Skill).where(Skill.namespace_id == namespace_id).where(Skill.slug == slug)
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


def list_skill_versions(
    db: Session,
    *,
    skill_id: int,
    limit: int | None = None,
    offset: int | None = None,
) -> list[SkillVersion]:
    stmt = select(SkillVersion).where(SkillVersion.skill_id == skill_id)
    # Prefer created_at for logical ordering; fall back to id for tests that
    # do not set created_at explicitly.
    stmt = stmt.order_by(SkillVersion.created_at.desc(), SkillVersion.id.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    return list(db.scalars(stmt).all())


def consume_skill_content(db: Session, content_id: int) -> bool:
    result = db.execute(
        update(SkillContent)
        .where(SkillContent.id == content_id)
        .where(SkillContent.state == "validated")
        .where(SkillContent.consumed_at.is_(None))
        .values(state="consumed", consumed_at=utcnow())
    )
    return bool(cast(Any, result).rowcount)


def create_skill_version(
    db: Session,
    *,
    skill_id: int,
    content_id: int,
    version: str,
    content_digest: str,
    metadata_digest: str,
    sealed_manifest_json: str,
    created_by_principal_id: int | None,
) -> SkillVersion:
    skill_version = SkillVersion(
        skill_id=skill_id,
        content_id=content_id,
        version=version,
        content_digest=content_digest,
        metadata_digest=metadata_digest,
        sealed_manifest_json=sealed_manifest_json,
        created_by_principal_id=created_by_principal_id,
    )
    db.add(skill_version)
    db.flush()
    return skill_version
