from __future__ import annotations

from pydantic import BaseModel, Field


class TransitionRequest(BaseModel):
    note: str = ''


class ReviewDecisionRequest(BaseModel):
    note: str = ''


class SubmissionCreateRequest(BaseModel):
    skill_name: str
    publisher: str = 'local'
    payload_summary: str = ''
    payload: dict = Field(default_factory=dict)


class StatusLogEntry(BaseModel):
    at: str
    actor_id: int | None = None
    actor_username: str | None = None
    actor_role: str | None = None
    from_status: str | None = None
    to: str
    note: str = ''


class ReviewView(BaseModel):
    id: int
    submission_id: int
    status: str
    note: str = ''
    requested_by: str | None = None
    reviewed_by: str | None = None
    created_at: str
    updated_at: str


class SubmissionView(BaseModel):
    id: int
    skill_name: str
    publisher: str
    status: str
    payload_summary: str = ''
    payload: dict = Field(default_factory=dict)
    created_by: str | None = None
    updated_by: str | None = None
    created_at: str
    updated_at: str
    approved_at: str | None = None
    status_log: list[StatusLogEntry] = Field(default_factory=list)
    review: ReviewView | None = None


class SkillPublishResponse(BaseModel):
    ok: bool
    skill_name: str
    status: str
    detail: str
