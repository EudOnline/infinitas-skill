from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PolicyOutcome:
    audience_type: str
    requested_review_mode: str
    review_requirement: str
    auto_activate: bool


def evaluate_exposure_policy(*, audience_type: str, requested_review_mode: str) -> PolicyOutcome:
    audience = str(audience_type or "").strip().lower()
    requested = str(requested_review_mode or "none").strip().lower() or "none"
    if requested not in {"none", "advisory", "blocking"}:
        raise ValueError(f"unsupported requested_review_mode: {requested_review_mode!r}")
    if audience not in {"private", "grant", "public", "authenticated"}:
        raise ValueError(f"unsupported audience_type: {audience_type!r}")

    if audience == "public":
        return PolicyOutcome(
            audience_type=audience,
            requested_review_mode=requested,
            review_requirement="blocking",
            auto_activate=False,
        )
    if audience == "grant":
        requirement = {"none": "none", "advisory": "advisory", "blocking": "blocking"}[requested]
        return PolicyOutcome(
            audience_type=audience,
            requested_review_mode=requested,
            review_requirement=requirement,
            auto_activate=requirement != "blocking",
        )
    return PolicyOutcome(
        audience_type=audience,
        requested_review_mode=requested,
        review_requirement="none",
        auto_activate=True,
    )
