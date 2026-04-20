from __future__ import annotations

import json

from pydantic import BaseModel, Field

from server.modules.agent_presets.models import AgentPresetSpec


def _load_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload if isinstance(item, str)]


class AgentPresetCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    display_name: str = Field(min_length=1, max_length=200)
    summary: str = ""
    runtime_family: str = "openclaw"
    supported_memory_modes: list[str] = Field(default_factory=lambda: ["none"])
    default_memory_mode: str = "none"
    pinned_skill_dependencies: list[str] = Field(default_factory=list)


class AgentPresetDraftCreateRequest(BaseModel):
    prompt: str = ""
    model: str = ""
    tools: list[str] = Field(default_factory=list)


class AgentPresetView(BaseModel):
    id: int
    skill_id: int
    registry_object_id: int
    slug: str
    display_name: str
    summary: str
    runtime_family: str
    supported_memory_modes: list[str] = Field(default_factory=list)
    default_memory_mode: str
    pinned_skill_dependencies: list[str] = Field(default_factory=list)

    @classmethod
    def from_model(
        cls,
        spec: AgentPresetSpec,
        *,
        slug: str,
        display_name: str,
        summary: str,
    ) -> "AgentPresetView":
        return cls(
            id=spec.id,
            skill_id=spec.skill_id,
            registry_object_id=spec.registry_object_id,
            slug=slug,
            display_name=display_name,
            summary=summary,
            runtime_family=spec.runtime_family,
            supported_memory_modes=_load_list(spec.supported_memory_modes_json),
            default_memory_mode=spec.default_memory_mode,
            pinned_skill_dependencies=_load_list(spec.pinned_skill_dependencies_json),
        )
