from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.models import Base, utcnow
from server.modules.shared.enums import ExposureMode, ReviewRequirement


class Exposure(Base):
    __tablename__ = 'exposures'
    __table_args__ = (
        Index('ix_exposures_release_id_mode', 'release_id', 'mode'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[int] = mapped_column(ForeignKey('releases.id'))
    mode: Mapped[str] = mapped_column(String(32), default=ExposureMode.PRIVATE.value)
    review_requirement: Mapped[str] = mapped_column(String(32), default=ReviewRequirement.NONE.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    release: Mapped['Release'] = relationship()
