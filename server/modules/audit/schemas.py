from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ActivityObjectView(BaseModel):
    id: int
    name: str | None = None
    kind: str | None = None


class ActivityReleaseView(BaseModel):
    id: int
    state: str | None = None


class ActivityEventView(BaseModel):
    id: int
    actor: str
    action: str
    object: ActivityObjectView | None = None
    release: ActivityReleaseView | None = None
    outcome: str
    timestamp: str | None = None
    aggregate_type: str
    aggregate_id: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ActivityListView(BaseModel):
    items: list[ActivityEventView] = Field(default_factory=list)
    total: int = 0
