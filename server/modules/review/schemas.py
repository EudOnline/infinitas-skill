from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from server.modules.review.models import ReviewCase, ReviewDecision


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _load_evidence(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


class ReviewCaseCreateRequest(BaseModel):
    mode: Literal["advisory", "blocking"] | None = None


class ReviewDecisionCreateRequest(BaseModel):
    decision: str
    note: str = ""
    evidence: dict = Field(default_factory=dict)


class ReviewDecisionView(BaseModel):
    id: int
    review_case_id: int
    reviewer_principal_id: int | None = None
    decision: str
    note: str = ""
    evidence: dict = Field(default_factory=dict)
    created_at: str

    @classmethod
    def from_model(cls, decision: ReviewDecision) -> "ReviewDecisionView":
        return cls(
            id=decision.id,
            review_case_id=decision.review_case_id,
            reviewer_principal_id=decision.reviewer_principal_id,
            decision=decision.decision,
            note=decision.note,
            evidence=_load_evidence(decision.evidence_json),
            created_at=_iso(decision.created_at) or "",
        )


class ReviewCaseView(BaseModel):
    id: int
    exposure_id: int
    policy_id: int | None = None
    mode: str
    state: str
    opened_by_principal_id: int | None = None
    opened_at: str
    closed_at: str | None = None
    decisions: list[ReviewDecisionView] = Field(default_factory=list)

    @classmethod
    def from_model(
        cls,
        review_case: ReviewCase,
        *,
        decisions: list[ReviewDecisionView] | None = None,
    ) -> "ReviewCaseView":
        return cls(
            id=review_case.id,
            exposure_id=review_case.exposure_id,
            policy_id=review_case.policy_id,
            mode=review_case.mode,
            state=review_case.state,
            opened_by_principal_id=review_case.opened_by_principal_id,
            opened_at=_iso(review_case.opened_at) or "",
            closed_at=_iso(review_case.closed_at),
            decisions=decisions or [],
        )
