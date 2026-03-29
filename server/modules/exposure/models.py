from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.models import Base, utcnow


class Exposure(Base):
    __tablename__ = "exposures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    audience_type: Mapped[str] = mapped_column(String(32), default="private")
    listing_mode: Mapped[str] = mapped_column(String(32), default="listed")
    install_mode: Mapped[str] = mapped_column(String(32), default="enabled")
    review_requirement: Mapped[str] = mapped_column(String(32), default="none")
    state: Mapped[str] = mapped_column(String(32), default="draft")
    requested_by_principal_id: Mapped[int | None] = mapped_column(ForeignKey("principals.id"), nullable=True)
    policy_snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    activated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __init__(self, **kwargs):
        audience_type = kwargs.get("audience_type")
        if kwargs.get("review_requirement") is None:
            kwargs["review_requirement"] = "blocking" if audience_type == "public" else "none"
        super().__init__(**kwargs)
