from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.models import Base, utcnow


class AccessGrant(Base):
    __tablename__ = 'access_grants'
    __table_args__ = (
        Index('ix_access_grants_release_id', 'release_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exposure_id: Mapped[int] = mapped_column(ForeignKey('exposures.id'))
    release_id: Mapped[int] = mapped_column(ForeignKey('releases.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    exposure: Mapped['Exposure'] = relationship()
    release: Mapped['Release'] = relationship()
    credentials: Mapped[list['AccessCredential']] = relationship(back_populates='grant')


class AccessCredential(Base):
    __tablename__ = 'access_credentials'
    __table_args__ = (
        Index('ix_access_credentials_token', 'token', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grant_id: Mapped[int] = mapped_column(ForeignKey('access_grants.id'))
    token: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    grant: Mapped[AccessGrant] = relationship(back_populates='credentials')
