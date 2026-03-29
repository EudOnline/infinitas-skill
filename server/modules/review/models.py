from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.models import Base, utcnow


class ReviewCase(Base):
    __tablename__ = 'review_cases'
    __table_args__ = (
        Index('ix_review_cases_exposure_id_status', 'exposure_id', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exposure_id: Mapped[int] = mapped_column(ForeignKey('exposures.id'))
    release_id: Mapped[int] = mapped_column(ForeignKey('releases.id'))
    status: Mapped[str] = mapped_column(String(64), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    exposure: Mapped['Exposure'] = relationship()
    release: Mapped['Release'] = relationship()
