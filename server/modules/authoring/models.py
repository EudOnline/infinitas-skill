from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models import Base, utcnow
from server.modules.access.models import Principal


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("namespace_id", "slug", name="uq_skills_namespace_id_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    namespace_id: Mapped[int] = mapped_column(ForeignKey("principals.id"), index=True)
    slug: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    default_visibility_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class SkillDraft(Base):
    __tablename__ = "skill_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    base_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="open")
    content_ref: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_skill_versions_skill_id_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    version: Mapped[str] = mapped_column(String(64))
    content_digest: Mapped[str] = mapped_column(String(255))
    metadata_digest: Mapped[str] = mapped_column(String(255))
    created_from_draft_id: Mapped[int | None] = mapped_column(
        ForeignKey("skill_drafts.id"),
        nullable=True,
    )
    created_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)


# Transitional alias while some registry code still imports Namespace from this module.
Namespace = Principal
