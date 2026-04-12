from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(32), default='contributor')
    token: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
        default=None,
    )
    light_bg_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    dark_bg_id: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Job(Base):
    __tablename__ = 'jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(64), default='queued', index=True)
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    release_id: Mapped[int | None] = mapped_column(
        ForeignKey('releases.id'),
        nullable=True,
        index=True,
    )
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    note: Mapped[str] = mapped_column(Text, default='')
    log: Mapped[str] = mapped_column(Text, default='')
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )

    requested_by: Mapped[User | None] = relationship(foreign_keys=[requested_by_user_id])


# Backwards-compatible registry model re-exports.
from server.modules.access.models import (  # noqa: E402
    AccessGrant,
    Credential,
    Principal,
    ServicePrincipal,
    Team,
    TeamMembership,
)
from server.modules.audit.models import AuditEvent  # noqa: E402
from server.modules.authoring.models import Namespace, Skill, SkillDraft, SkillVersion  # noqa: E402
from server.modules.exposure.models import Exposure  # noqa: E402
from server.modules.release.models import Artifact, Release  # noqa: E402
from server.modules.review.models import (  # noqa: E402
    ReviewCase,
    ReviewDecision,
    ReviewPolicy,
)

__all__ = [
    "AccessGrant",
    "Artifact",
    "AuditEvent",
    "Base",
    "Credential",
    "Exposure",
    "Job",
    "Namespace",
    "Principal",
    "Release",
    "ReviewCase",
    "ReviewDecision",
    "ReviewPolicy",
    "ServicePrincipal",
    "Skill",
    "SkillDraft",
    "SkillVersion",
    "Team",
    "TeamMembership",
    "User",
    "utcnow",
]
