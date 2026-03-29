from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.models import Base, utcnow


class ReviewPolicy(Base):
    __tablename__ = "review_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rules_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewCase(Base):
    __tablename__ = "review_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exposure_id: Mapped[int] = mapped_column(ForeignKey("exposures.id"), index=True)
    policy_id: Mapped[int | None] = mapped_column(ForeignKey("review_policies.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(32), default="blocking")
    state: Mapped[str] = mapped_column(String(32), default="open")
    opened_by_principal_id: Mapped[int | None] = mapped_column(ForeignKey("principals.id"), nullable=True)
    opened_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_case_id: Mapped[int] = mapped_column(ForeignKey("review_cases.id"), index=True)
    reviewer_principal_id: Mapped[int | None] = mapped_column(ForeignKey("principals.id"), nullable=True)
    decision: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)
