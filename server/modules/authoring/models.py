from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from server.model_base import Base, utcnow


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("namespace_id", "slug", name="uq_skills_namespace_id_slug"),
        Index("ix_skills_namespace_id_slug", "namespace_id", "slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    namespace_id: Mapped[int] = mapped_column(ForeignKey("principals.id"))
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


class SkillContent(Base):
    __tablename__ = "skill_contents"
    __table_args__ = (
        UniqueConstraint("public_id", name="uq_skill_contents_public_id"),
        Index("ix_skill_contents_skill_id_state", "skill_id", "state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(String(64))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    storage_uri: Mapped[str] = mapped_column(String(1000))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    declared_version: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="validated")
    created_by_principal_id: Mapped[int] = mapped_column(ForeignKey("principals.id"), index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)
    consumed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_skill_versions_skill_id_version"),
        Index("ix_skill_versions_skill_id_version", "skill_id", "version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    content_id: Mapped[int] = mapped_column(ForeignKey("skill_contents.id"), unique=True)
    version: Mapped[str] = mapped_column(String(64))
    content_digest: Mapped[str] = mapped_column(String(255))
    metadata_digest: Mapped[str] = mapped_column(String(255))
    sealed_manifest_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)
