from __future__ import annotations

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.models import Base, utcnow


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (UniqueConstraint("skill_version_id", name="uq_releases_skill_version_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_version_id: Mapped[int] = mapped_column(ForeignKey("skill_versions.id"), index=True)
    state: Mapped[str] = mapped_column(String(32), default="preparing")
    format_version: Mapped[str] = mapped_column(String(32), default="1")
    manifest_artifact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bundle_artifact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signature_artifact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_artifact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ready_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    platform_compatibility_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("principals.id"),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[int] = mapped_column(ForeignKey("releases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    storage_uri: Mapped[str] = mapped_column(Text, default="")
    sha256: Mapped[str] = mapped_column(String(128), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), default=utcnow)
