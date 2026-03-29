from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.models import Base, utcnow


class Namespace(Base):
    __tablename__ = 'namespaces'
    __table_args__ = (
        Index('ix_namespaces_slug', 'slug', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    skills: Mapped[list['Skill']] = relationship(back_populates='namespace')


class Skill(Base):
    __tablename__ = 'skills'
    __table_args__ = (
        Index('ix_skills_namespace_id_slug', 'namespace_id', 'slug', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    namespace_id: Mapped[int] = mapped_column(ForeignKey('namespaces.id'))
    slug: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    namespace: Mapped[Namespace] = relationship(back_populates='skills')
    drafts: Mapped[list['SkillDraft']] = relationship(back_populates='skill')
    versions: Mapped[list['SkillVersion']] = relationship(back_populates='skill')


class SkillDraft(Base):
    __tablename__ = 'skill_drafts'
    __table_args__ = (
        Index('ix_skill_drafts_skill_id_state', 'skill_id', 'state'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey('skills.id'))
    state: Mapped[str] = mapped_column(String(64), default='draft')
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    skill: Mapped[Skill] = relationship(back_populates='drafts')


class SkillVersion(Base):
    __tablename__ = 'skill_versions'
    __table_args__ = (
        Index('ix_skill_versions_skill_id_version', 'skill_id', 'version', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey('skills.id'))
    version: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    skill: Mapped[Skill] = relationship(back_populates='versions')
    releases: Mapped[list['Release']] = relationship(back_populates='skill_version')
