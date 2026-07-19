from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from server.model_base import utcnow
from server.modules.authoring.models import Skill, SkillContent, SkillVersion


def get_skill(db: Session, skill_id: int) -> Skill | None:
    return db.get(Skill, skill_id)


def get_skill_content_by_public_id(db: Session, public_id: str) -> SkillContent | None:
    return db.scalar(select(SkillContent).where(SkillContent.public_id == public_id))


def pending_content_usage(
    db: Session,
    *,
    skill_id: int,
    principal_id: int,
) -> tuple[int, int]:
    skill_count = db.scalar(
        select(func.count(SkillContent.id))
        .where(SkillContent.skill_id == skill_id)
        .where(SkillContent.state == "validated")
        .where(SkillContent.consumed_at.is_(None))
    )
    principal_bytes = db.scalar(
        select(func.sum(SkillContent.size_bytes))
        .where(SkillContent.created_by_principal_id == principal_id)
        .where(SkillContent.state == "validated")
        .where(SkillContent.consumed_at.is_(None))
    )
    return int(skill_count or 0), int(principal_bytes or 0)


def list_expired_skill_contents(
    db: Session,
    *,
    cutoff: datetime,
    limit: int,
    principal_id: int | None = None,
) -> list[SkillContent]:
    query = (
        select(SkillContent)
        .where(SkillContent.state == "validated")
        .where(SkillContent.consumed_at.is_(None))
        .where(SkillContent.created_at < cutoff)
        .order_by(SkillContent.created_at.asc(), SkillContent.id.asc())
        .limit(limit)
    )
    if principal_id is not None:
        query = query.where(SkillContent.created_by_principal_id == principal_id)
    return list(db.scalars(query).all())


def active_storage_uri_is_referenced(db: Session, storage_uri: str) -> bool:
    query = (
        select(SkillContent.id)
        .where(SkillContent.storage_uri == storage_uri)
        .where(SkillContent.state != "expired")
    )
    return db.scalar(query.limit(1)) is not None


def create_skill_content(
    db: Session,
    *,
    public_id: str,
    skill_id: int,
    storage_uri: str,
    sha256: str,
    size_bytes: int,
    declared_version: str,
    metadata_json: str,
    created_by_principal_id: int,
) -> SkillContent:
    content = SkillContent(
        public_id=public_id,
        skill_id=skill_id,
        storage_uri=storage_uri,
        sha256=sha256,
        size_bytes=size_bytes,
        declared_version=declared_version,
        metadata_json=metadata_json,
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
