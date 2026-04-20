from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.models import Base


class AgentCodeSpec(Base):
    __tablename__ = "agent_code_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registry_object_id: Mapped[int] = mapped_column(ForeignKey("registry_objects.id"), unique=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), unique=True)
    runtime_family: Mapped[str] = mapped_column(String(64), default="openclaw")
    language: Mapped[str] = mapped_column(String(64), default="python")
    entrypoint: Mapped[str] = mapped_column(String(255), default="")
    external_source_json: Mapped[str] = mapped_column(Text, default="{}")
