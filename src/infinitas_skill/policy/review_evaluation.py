"""Review decision projection and quorum evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from infinitas_skill.root import ROOT


def _classify_decisions(
    latest: dict[str, dict[str, Any]],
    reviewers: dict[str, dict[str, Any]],
    *,
    owner: str | None,
    require_distinct_owner: bool,
    owner_fallback_allowed: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    from infinitas_skill.policy.reviews import ALLOWED_DECISIONS

    approvals: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    ignored: list[dict[str, Any]] = []
    covered_groups: list[str] = []
    for reviewer, entry in sorted(latest.items()):
        reviewer_groups = reviewers.get(reviewer, {}).get("groups", [])
        reasons = []
        decision = entry.get("decision")
        if reviewer not in reviewers:
            reasons.append("unconfigured reviewer")
        if decision not in ALLOWED_DECISIONS:
            reasons.append("invalid decision")
        if reviewer == owner and require_distinct_owner and not owner_fallback_allowed:
            reasons.append("reviewer is owner")
        item = {
            "reviewer": reviewer,
            "decision": decision,
            "at": entry.get("at"),
            "note": entry.get("note"),
            "groups": reviewer_groups,
            "source": entry.get("source"),
            "source_kind": entry.get("source_kind"),
            "source_ref": entry.get("source_ref"),
            "url": entry.get("url"),
            "counted": not reasons,
            "reasons": reasons,
        }
        if reasons:
            ignored.append(item)
        elif decision == "approved":
            approvals.append(item)
            covered_groups.extend(group for group in reviewer_groups if group not in covered_groups)
        elif decision == "rejected":
            rejections.append(item)
    return approvals, rejections, ignored, covered_groups


def _effective_state(*, blocking_rejections: int, gate_pass: bool, has_activity: bool) -> str:
    if blocking_rejections:
        return "rejected"
    if gate_pass:
        return "approved"
    return "under-review" if has_activity else "draft"


def evaluate_review_state(
    skill_dir: Path,
    *,
    root: Path = ROOT,
    stage: str | None = None,
    as_active: bool = False,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from infinitas_skill.policy.review_evidence import ReviewEvidenceError
    from infinitas_skill.policy.reviews import (
        ReviewPolicyError,
        configured_reviewers,
        effective_quorum_rule,
        latest_distinct_entries,
        load_meta,
        load_promotion_policy,
        owner_review_unavoidable,
        review_decision_entries,
    )

    resolved_dir = Path(skill_dir).resolve()
    resolved_policy = policy or load_promotion_policy(root)
    meta = load_meta(resolved_dir)
    try:
        reviews, entries = review_decision_entries(resolved_dir)
    except ReviewEvidenceError as exc:
        raise ReviewPolicyError([str(exc)]) from exc
    latest = latest_distinct_entries(entries)
    groups, reviewers = configured_reviewers(resolved_policy, root=root)
    reviews_cfg = resolved_policy.get("reviews", {})
    actual_stage = meta.get("status") or resolved_dir.parent.name
    evaluated_stage = "active" if as_active else (stage or actual_stage)
    owner = meta.get("owner")
    risk_level = meta.get("risk_level")
    normalized_risk = risk_level if isinstance(risk_level, str) else "medium"
    quorum = effective_quorum_rule(resolved_policy, evaluated_stage, normalized_risk)
    owner_fallback = bool(reviews_cfg.get("allow_owner_when_no_distinct_reviewer")) and (
        owner_review_unavoidable(
            owner, reviewers, quorum.get("required_groups", []), quorum.get("min_approvals", 0)
        )
    )
    approvals, rejections, ignored, covered_groups = _classify_decisions(
        latest,
        reviewers,
        owner=owner,
        require_distinct_owner=bool(reviews_cfg.get("reviewer_must_differ_from_owner")),
        owner_fallback_allowed=owner_fallback,
    )
    required_groups = quorum.get("required_groups", [])
    missing_groups = [group for group in required_groups if group not in covered_groups]
    quorum_met = len(approvals) >= quorum.get("min_approvals", 0) and not missing_groups
    reviews_file_present = (resolved_dir / "reviews.json").is_file()
    blocking_rejections = len(rejections) if reviews_cfg.get("block_on_rejection", False) else 0
    gate_pass = (
        (not reviews_cfg.get("require_reviews_file") or reviews_file_present)
        and quorum_met
        and blocking_rejections == 0
    )
    latest_decisions = sorted(approvals + rejections + ignored, key=lambda item: item["reviewer"])
    return {
        "skill": meta.get("name", resolved_dir.name),
        "version": meta.get("version"),
        "owner": owner,
        "risk_level": meta.get("risk_level"),
        "actual_stage": actual_stage,
        "evaluated_stage": evaluated_stage,
        "declared_review_state": meta.get("review_state"),
        "effective_review_state": _effective_state(
            blocking_rejections=blocking_rejections,
            gate_pass=gate_pass,
            has_activity=bool(reviews.get("requests") or entries),
        ),
        "reviews_file_present": reviews_file_present,
        "review_request_count": len(reviews.get("requests", [])),
        "required_approvals": quorum.get("min_approvals", 0),
        "required_groups": required_groups,
        "covered_groups": covered_groups,
        "missing_groups": missing_groups,
        "approval_count": len(approvals),
        "rejection_count": len(rejections),
        "blocking_rejection_count": blocking_rejections,
        "quorum_met": quorum_met,
        "review_gate_pass": gate_pass,
        "latest_decisions": latest_decisions,
        "ignored_decisions": ignored,
        "configured_groups": groups,
        "configured_reviewers": sorted(reviewers),
    }
