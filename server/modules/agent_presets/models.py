from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.models import Base


class AgentPresetSpec(Base):
    __tablename__ = "agent_preset_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    registry_object_id: Mapped[int] = mapped_column(ForeignKey("registry_objects.id"), unique=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), unique=True)
    runtime_family: Mapped[str] = mapped_column(String(64), default="openclaw")
    supported_memory_modes_json: Mapped[str] = mapped_column(Text, default="[]")
    default_memory_mode: Mapped[str] = mapped_column(String(32), default="none")
    pinned_skill_dependencies_json: Mapped[str] = mapped_column(Text, default="[]")
    default_prompt: Mapped[str] = mapped_column(Text, default="")
    default_model: Mapped[str] = mapped_column(String(128), default="")
    default_tools_json: Mapped[str] = mapped_column(Text, default="[]")

