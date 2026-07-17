from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.model_base import Base


class Exposure(Base):
    __tablename__ = "exposures"
    __table_args__ = (
        Index(
            "ix_exposures_release_id_audience_type_state",
            "release_id",
            "audience_type",
            "state",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"))
    audience_type: Mapped[str] = mapped_column(String(32), default="private")
    listing_mode: Mapped[str] = mapped_column(String(32), default="listed")
    install_mode: Mapped[str] = mapped_column(String(32), default="enabled")
    review_requirement: Mapped[str] = mapped_column(String(32), default="none")
    state: Mapped[str] = mapped_column(String(32), default="draft")
    requested_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
        index=True,
    )
    policy_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs: Any) -> None:
        audience_type = kwargs.get("audience_type")
        if kwargs.get("review_requirement") is None:
            kwargs["review_requirement"] = "blocking" if audience_type == "public" else "none"
        super().__init__(**kwargs)
