"""Reviewer recommendation helpers for review status commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infinitas_skill.root import ROOT

from .review_evaluation import evaluate_review_state
from .reviews import (
    configured_reviewers,
    effective_quorum_rule,
    load_promotion_policy,
    owner_review_unavoidable,
)

JsonDict = dict[str, Any]


def _eligible_sort_key(item: JsonDict) -> tuple[int, str, str]:
    latest = item.get("latest_decision_at")
    return (0 if not latest else 1, latest or "", item.get("reviewer") or "")


def _excluded_sort_key(item: JsonDict) -> tuple[str, str]:
    return (",".join(item.get("reasons") or []), item.get("reviewer") or "")


def _target_groups(evaluation: JsonDict, groups: dict[str, JsonDict]) -> tuple[list[str], int]:
    required_groups = list(evaluation.get("required_groups") or [])
    target_groups = list(evaluation.get("missing_groups") or [])
    approval_gap = max(
        (evaluation.get("required_approvals") or 0) - (evaluation.get("approval_count") or 0),
        0,
    )
    if required_groups and approval_gap > len(target_groups):
        target_groups.extend(
            group_name for group_name in required_groups if group_name not in target_groups
        )
    return target_groups or required_groups or sorted(groups), approval_gap


def _recommend_group(
    group_name: str,
    group_data: JsonDict,
    *,
    reviewers: dict[str, JsonDict],
    evaluation: JsonDict,
    reviews_cfg: JsonDict,
    owner_fallback_allowed: bool,
    latest_by_reviewer: dict[str, JsonDict],
    counted_reviewers: set[str],
) -> tuple[JsonDict, JsonDict | None]:
    eligible_reviewers: list[dict[str, Any]] = []
    excluded_reviewers: list[dict[str, Any]] = []
    for reviewer in group_data.get("resolved_members", []):
        reasons: list[str] = []
        if (
            reviewer == evaluation.get("owner")
            and reviews_cfg.get("reviewer_must_differ_from_owner")
            and not owner_fallback_allowed
        ):
            reasons.append("owner-conflict")
        if reviewer in counted_reviewers:
            reasons.append("already-counted-reviewer")
        candidate = {
            "reviewer": reviewer,
            "groups": (reviewers.get(reviewer) or {}).get("groups", []),
            "latest_decision": latest_by_reviewer.get(reviewer, {}).get("decision"),
            "latest_decision_at": latest_by_reviewer.get(reviewer, {}).get("at"),
            "reasons": reasons,
        }
        (excluded_reviewers if reasons else eligible_reviewers).append(candidate)
    eligible_reviewers.sort(key=_eligible_sort_key)
    excluded_reviewers.sort(key=_excluded_sort_key)
    recommendation = {
        "group": group_name,
        "description": group_data.get("description"),
        "eligible_reviewers": eligible_reviewers,
        "excluded_reviewers": excluded_reviewers,
    }
    escalation = None
    if not eligible_reviewers:
        escalation = {
            "group": group_name,
            "reason": "no-eligible-reviewer",
            "message": (
                f"No eligible reviewer is currently available for group {group_name}; "
                "update team membership or use a reviewed exception path."
            ),
        }
    return recommendation, escalation


def recommend_reviewers(
    skill_dir: Path,
    *,
    root: Path = ROOT,
    stage: str | None = None,
    as_active: bool = False,
    policy: JsonDict | None = None,
) -> JsonDict:
    root = Path(root).resolve()
    skill_dir = Path(skill_dir).resolve()
    policy = policy or load_promotion_policy(root)
    evaluation = evaluate_review_state(
        skill_dir,
        root=root,
        stage=stage,
        as_active=as_active,
        policy=policy,
    )
    groups, reviewers = configured_reviewers(policy, root=root)
    reviews_cfg = policy.get("reviews", {}) if isinstance(policy, dict) else {}
    evaluated_stage = evaluation.get("evaluated_stage")
    risk_level = evaluation.get("risk_level")
    quorum_rule = effective_quorum_rule(
        policy,
        evaluated_stage if isinstance(evaluated_stage, str) else "active",
        risk_level if isinstance(risk_level, str) else "medium",
    )
    owner_fallback_allowed = bool(
        reviews_cfg.get("allow_owner_when_no_distinct_reviewer")
    ) and owner_review_unavoidable(
        evaluation.get("owner") if isinstance(evaluation.get("owner"), str) else None,
        reviewers,
        quorum_rule.get("required_groups", []),
        quorum_rule.get("min_approvals", 0),
    )

    latest_by_reviewer: dict[str, JsonDict] = {}
    counted_reviewers: set[str] = set()
    for item in evaluation.get("latest_decisions", []):
        reviewer = item.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer:
            continue
        latest_by_reviewer[reviewer] = item
        if item.get("counted"):
            counted_reviewers.add(reviewer)
    target_groups, approval_gap = _target_groups(evaluation, groups)

    group_recommendations: list[JsonDict] = []
    escalations: list[JsonDict] = []
    for group_name in target_groups:
        group_data = groups.get(group_name) or {}
        recommendation, escalation = _recommend_group(
            group_name,
            group_data,
            reviewers=reviewers,
            evaluation=evaluation,
            reviews_cfg=reviews_cfg,
            owner_fallback_allowed=owner_fallback_allowed,
            latest_by_reviewer=latest_by_reviewer,
            counted_reviewers=counted_reviewers,
        )
        group_recommendations.append(recommendation)
        if escalation is not None:
            escalations.append(escalation)

    return {
        "skill": evaluation.get("skill"),
        "version": evaluation.get("version"),
        "actual_stage": evaluation.get("actual_stage"),
        "evaluated_stage": evaluation.get("evaluated_stage"),
        "owner": evaluation.get("owner"),
        "required_approvals": evaluation.get("required_approvals"),
        "approval_count": evaluation.get("approval_count"),
        "approval_gap": approval_gap,
        "required_groups": evaluation.get("required_groups", []),
        "missing_groups": evaluation.get("missing_groups", []),
        "group_recommendations": group_recommendations,
        "escalations": escalations,
    }


def render_reviewer_recommendations(payload: JsonDict) -> str:
    lines: list[str] = []
    for group in payload.get("group_recommendations", []):
        group_name = group.get("group")
        eligible = group.get("eligible_reviewers") or []
        excluded = group.get("excluded_reviewers") or []
        if eligible:
            lines.append(
                f"recommended reviewers [{group_name}]: "
                + ", ".join(item.get("reviewer") or "" for item in eligible)
            )
        else:
            lines.append(f"recommended reviewers [{group_name}]: none")
        for item in excluded:
            reason_text = ",".join(item.get("reasons") or [])
            lines.append(f"  exclude {item.get('reviewer')}: {reason_text}")
    for item in payload.get("escalations", []):
        lines.append(f"escalation [{item.get('group')}]: {item.get('message')}")
    return "\n".join(lines)


__all__ = [
    "recommend_reviewers",
    "render_reviewer_recommendations",
]
