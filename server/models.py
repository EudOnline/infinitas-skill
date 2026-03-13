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
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Submission(Base):
    __tablename__ = 'submissions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_name: Mapped[str] = mapped_column(String(200), index=True)
    publisher: Mapped[str] = mapped_column(String(200), default='local')
    status: Mapped[str] = mapped_column(String(64), default='draft', index=True)
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    payload_summary: Mapped[str] = mapped_column(Text, default='')
    status_log_json: Mapped[str] = mapped_column(Text, default='[]')
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    review_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_user_id])
    updated_by: Mapped[User | None] = relationship(foreign_keys=[updated_by_user_id])


class Review(Base):
    __tablename__ = 'reviews'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey('submissions.id'), index=True)
    status: Mapped[str] = mapped_column(String(64), default='pending', index=True)
    note: Mapped[str] = mapped_column(Text, default='')
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    submission: Mapped[Submission] = relationship()
    requested_by: Mapped[User | None] = relationship(foreign_keys=[requested_by_user_id])
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_user_id])


class Job(Base):
    __tablename__ = 'jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(64), default='queued', index=True)
    payload_json: Mapped[str] = mapped_column(Text, default='{}')
    submission_id: Mapped[int | None] = mapped_column(ForeignKey('submissions.id'), nullable=True, index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    note: Mapped[str] = mapped_column(Text, default='')
    log: Mapped[str] = mapped_column(Text, default='')
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    submission: Mapped[Submission | None] = relationship()
    requested_by: Mapped[User | None] = relationship(foreign_keys=[requested_by_user_id])
