from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.models import Base, utcnow


class Release(Base):
    __tablename__ = 'releases'
    __table_args__ = (
        Index('ix_releases_skill_version_id_state', 'skill_version_id', 'state'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_version_id: Mapped[int] = mapped_column(ForeignKey('skill_versions.id'))
    state: Mapped[str] = mapped_column(String(64), default='draft')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    skill_version: Mapped['SkillVersion'] = relationship(back_populates='releases')
    artifacts: Mapped[list['Artifact']] = relationship(back_populates='release')


class Artifact(Base):
    __tablename__ = 'artifacts'
    __table_args__ = (
        Index('ix_artifacts_release_id_kind_digest', 'release_id', 'kind', 'digest', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[int] = mapped_column(ForeignKey('releases.id'))
    kind: Mapped[str] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    release: Mapped[Release] = relationship(back_populates='artifacts')
