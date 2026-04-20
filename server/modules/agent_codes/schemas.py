from __future__ import annotations

import json

from pydantic import BaseModel, Field

from server.modules.agent_codes.models import AgentCodeSpec


def _load_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


class AgentCodeCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    display_name: str = Field(min_length=1, max_length=200)
    summary: str = ""
    runtime_family: str = "openclaw"
    language: str = "python"
    entrypoint: str = Field(min_length=1, max_length=255)


class AgentCodeDraftCreateRequest(BaseModel):
    content_ref: str = Field(min_length=1)


class AgentCodeView(BaseModel):
    id: int
    skill_id: int
    registry_object_id: int
    slug: str
    display_name: str
    summary: str
    runtime_family: str
    language: str
    entrypoint: str
    external_source: dict

    @classmethod
    def from_model(
        cls,
        spec: AgentCodeSpec,
        *,
        slug: str,
        display_name: str,
        summary: str,
    ) -> "AgentCodeView":
        return cls(
            id=spec.id,
            skill_id=spec.skill_id,
            registry_object_id=spec.registry_object_id,
            slug=slug,
            display_name=display_name,
            summary=summary,
            runtime_family=spec.runtime_family,
            language=spec.language,
            entrypoint=spec.entrypoint,
            external_source=_load_json(spec.external_source_json),
        )
