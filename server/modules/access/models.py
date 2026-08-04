from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.model_base import Base, utcnow


class AccessGrant(Base):
    __tablename__ = "access_grants"
    __table_args__ = (
        Index(
            "ix_access_grants_exposure_id_grant_type_state",
            "exposure_id",
            "grant_type",
            "state",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exposure_id: Mapped[int] = mapped_column(ForeignKey("exposures.id"))
    grant_type: Mapped[str] = mapped_column(String(32))
    subject_ref: Mapped[str] = mapped_column(String(255))
    constraints_json: Mapped[str] = mapped_column(Text, default="{}")
    state: Mapped[str] = mapped_column(String(32), default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RateLimitEntry(Base):
    """Shared rate-limit bucket storage owned by the access domain."""

    __tablename__ = "rate_limit_entries"
    __table_args__ = (UniqueConstraint("key", name="uq_rate_limit_entries_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
