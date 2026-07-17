"""Promotion-policy report assembly."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.root import ROOT

from .exception_policy import ExceptionPolicyError, load_exception_policy, match_active_exceptions
from .policy_pack import PolicyPackError, load_policy_domain_resolution
from .review_evaluation import evaluate_review_state
from .reviews import ReviewPolicyError
from .trace import build_policy_trace


def _rule(rule_text: str, *, id: str | None = None, value: Any = None, **extra: Any) -> dict:
    item = {"rule": rule_text}
    if id is not None:
        item["id"] = id
    if value is not None:
        item["value"] = value
    for key, raw in extra.items():
        if raw is not None:
            item[key] = raw
    return item


def _add_issue(
    issues: list[dict],
    rule_id: str,
    message: str,
    *,
    rule: str,
    value: Any = None,
    next_action: str | None = None,
) -> None:
    issues.append(
        {
            "id": rule_id,
            "message": message,
            "rule": rule,
            "value": value,
            "next_action": next_action,
        }
    )


def _skipped_report(skill_dir: Path, root: Path, meta: dict, stage: str) -> dict:
    trace = build_policy_trace(
        domain="promotion_policy",
        decision="skipped",
        summary="promotion policy is enforced only for active-stage evaluation",
        effective_sources=[],
        applied_rules=[_rule("promotion checks are skipped outside active-stage evaluation")],
        reasons=[
            "use --as-active or run the check against an active skill to enforce promotion policy"
        ],
        next_actions=["rerun with --as-active if you want active-stage gating"],
        exceptions=[],
    )
    return {
        "skill": meta.get("name", skill_dir.name),
        "skill_path": str(skill_dir.relative_to(root)),
        "evaluated_stage": stage,
        "passed": True,
        "error_count": 0,
        "errors": [],
        "evaluation": None,
        "exception_usage": [],
        "policy_trace": trace,
    }


def _collect_review_issues(
    skill_dir: Path, evaluation: dict, reviews_cfg: dict, issues: list[dict]
) -> None:
    if reviews_cfg.get("require_reviews_file") and not (skill_dir / "reviews.json").is_file():
        _add_issue(
            issues,
            "missing-reviews-file",
            f"{skill_dir}: active skill requires reviews.json",
            rule="reviews file is required for active skills",
            value="missing reviews.json",
            next_action="add reviews.json before promoting this skill",
        )
    if evaluation["approval_count"] < evaluation["required_approvals"]:
        required = evaluation["required_approvals"]
        _add_issue(
            issues,
            "minimum-approvals",
            f"{skill_dir}: active skill requires at least {required} counted approval(s)",
            rule="minimum counted approvals must be met",
            value=f"{evaluation['approval_count']}/{evaluation['required_approvals']}",
            next_action="collect the required number of counted approvals",
        )
    if evaluation["missing_groups"]:
        joined = ", ".join(evaluation["missing_groups"])
        _add_issue(
            issues,
            "required-reviewer-groups",
            f"{skill_dir}: active skill is missing reviewer group coverage for {joined}",
            rule="required reviewer groups must be covered",
            value=joined,
            next_action="request review from the missing reviewer groups",
        )
    if reviews_cfg.get("block_on_rejection", False) and evaluation["blocking_rejection_count"]:
        _add_issue(
            issues,
            "blocking-rejections",
            f"{skill_dir}: active skill has blocking rejection(s)",
            rule="blocking rejections must be resolved before promotion",
            value=evaluation["blocking_rejection_count"],
            next_action="resolve or supersede the blocking rejection decisions",
        )
    if not evaluation["review_gate_pass"] and not issues:
        _add_issue(
            issues,
            "review-quorum",
            f"{skill_dir}: active skill does not satisfy computed review quorum",
            rule="computed review quorum must pass",
            next_action="inspect the review quorum inputs and latest decisions",
        )


def _collect_required_metadata_issues(
    skill_dir: Path, meta: dict, evaluation: dict, requirements: dict, issues: list[dict]
) -> None:
    allowed_states = requirements.get("review_state", [])
    if evaluation["effective_review_state"] not in allowed_states:
        _add_issue(
            issues,
            "effective-review-state",
            f"{skill_dir}: review_state must be one of {allowed_states}",
            rule="effective review_state must be allowed for promotion",
            value=evaluation["effective_review_state"],
        )
    required_files = (("require_changelog", "CHANGELOG.md", "missing-changelog", "CHANGELOG.md"),)
    for flag, filename, issue_id, label in required_files:
        if requirements.get(flag) and not (skill_dir / filename).is_file():
            _add_issue(
                issues,
                issue_id,
                f"{skill_dir}: active skill requires {label}",
                rule=f"{label} is required for active promotion",
            )
    if requirements.get("require_smoke_test"):
        smoke = meta.get("tests", {}).get("smoke", "tests/smoke.md")
        if not (skill_dir / smoke).is_file():
            _add_issue(
                issues,
                "missing-smoke-test",
                f"{skill_dir}: active skill requires smoke test {smoke}",
                rule="smoke test file is required for active promotion",
                value=smoke,
            )
    if requirements.get("require_owner") and not meta.get("owner"):
        _add_issue(
            issues,
            "missing-owner",
            f"{skill_dir}: active skill requires owner",
            rule="owner metadata is required for active promotion",
        )


def _collect_high_risk_issues(
    skill_dir: Path, meta: dict, policy: dict, issues: list[dict]
) -> None:
    if meta.get("risk_level") != "high":
        return
    high = policy.get("high_risk_active_requires", {})
    high = high if isinstance(high, dict) else {}
    maintainers = meta.get("maintainers", []) or []
    minimum = high.get("min_maintainers", 0)
    if len(maintainers) < minimum:
        _add_issue(
            issues,
            "minimum-maintainers",
            f"{skill_dir}: high-risk active skill requires at least {minimum} maintainer(s)",
            rule="high-risk skills require minimum maintainer coverage",
            value=f"{len(maintainers)}/{minimum}",
        )
    if high.get("require_requires_block") and not isinstance(meta.get("requires"), dict):
        _add_issue(
            issues,
            "missing-requires-block",
            f"{skill_dir}: high-risk active skill requires a requires block",
            rule="high-risk skills require a requires block",
        )


def _apply_exceptions(
    meta: dict, issues: list[dict], *, root: Path, exception_policy: dict
) -> tuple[list[dict], list[dict]]:
    usage = match_active_exceptions(
        "promotion",
        meta,
        [item["id"] for item in issues],
        root=root,
        policy=exception_policy,
    )
    waived = {
        rule_id
        for item in usage
        for rule_id in item.get("matched_rules", [])
        if isinstance(rule_id, str) and rule_id
    }
    return usage, [item for item in issues if item.get("id") not in waived]


def _report_trace(
    *,
    policy_resolution: dict,
    requirements: dict,
    reviews_cfg: dict,
    evaluation: dict,
    remaining: list[dict],
    exception_usage: list[dict],
) -> dict:
    errors = [item["message"] for item in remaining]
    next_actions = list(
        dict.fromkeys(
            item["next_action"]
            for item in remaining
            if isinstance(item.get("next_action"), str) and item["next_action"]
        )
    )
    return build_policy_trace(
        domain="promotion_policy",
        decision="allow" if not errors else "deny",
        summary=(
            "promotion policy passed for active skill"
            if not errors
            else f"promotion policy blocked by {len(errors)} issue(s)"
        ),
        effective_sources=policy_resolution.get("effective_sources"),
        applied_rules=[
            _rule(
                "active skill review_state must satisfy active_requires.review_state",
                id="effective-review-state",
                value=",".join(requirements.get("review_state", [])),
            ),
            _rule(
                "review quorum is computed from latest distinct reviewer decisions",
                id="review-quorum",
                value="enabled",
            ),
            _rule(
                "required reviewer groups must be covered",
                id="required-reviewer-groups",
                value=",".join(evaluation.get("required_groups", [])) or "-",
            ),
            _rule(
                "minimum approvals must be met",
                id="minimum-approvals",
                value=evaluation.get("required_approvals", 0),
            ),
            _rule(
                "blocking rejections are enforced",
                id="blocking-rejections",
                value=bool(reviews_cfg.get("block_on_rejection", False)),
            ),
        ],
        blocking_rules=[
            _rule(
                item["rule"],
                id=item.get("id"),
                value=item.get("value"),
                message=item.get("message"),
            )
            for item in remaining
        ],
        reasons=[
            f"effective_review_state={evaluation.get('effective_review_state')}",
            f"approval_count={evaluation.get('approval_count')}",
            f"blocking_rejections={evaluation.get('blocking_rejection_count')}",
            f"exceptions_applied={len(exception_usage)}",
        ],
        next_actions=next_actions,
        exceptions=exception_usage,
    )


def collect_skill_report(
    skill_dir: Path,
    *,
    as_active: bool = False,
    root: Path = ROOT,
    exception_policy: dict | None = None,
) -> dict:
    skill_dir = Path(skill_dir).resolve()
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    stage = "active" if as_active else skill_dir.parent.name
    try:
        policy_resolution = load_policy_domain_resolution(root, "promotion_policy")
    except PolicyPackError as exc:
        raise ReviewPolicyError(exc.errors) from exc
    if stage != "active":
        report = _skipped_report(skill_dir, root, meta, stage)
        report["policy_trace"]["effective_sources"] = policy_resolution.get("effective_sources")
        return report

    policy = policy_resolution["effective"]
    reviews_cfg = policy.get("reviews", {})
    requirements = policy.get("active_requires", {})
    evaluation = evaluate_review_state(skill_dir, root=root, stage="active", policy=policy)
    issues: list[dict] = []
    _collect_review_issues(skill_dir, evaluation, reviews_cfg, issues)
    _collect_required_metadata_issues(skill_dir, meta, evaluation, requirements, issues)
    _collect_high_risk_issues(skill_dir, meta, policy, issues)
    if exception_policy is None:
        try:
            exception_policy = load_exception_policy(root)
        except ExceptionPolicyError as exc:
            raise ReviewPolicyError(exc.errors) from exc
    exception_usage, remaining = _apply_exceptions(
        meta, issues, root=root, exception_policy=exception_policy
    )
    errors = [item["message"] for item in remaining]
    trace = _report_trace(
        policy_resolution=policy_resolution,
        requirements=requirements,
        reviews_cfg=reviews_cfg,
        evaluation=evaluation,
        remaining=remaining,
        exception_usage=exception_usage,
    )
    return {
        "skill": meta.get("name", skill_dir.name),
        "skill_path": str(skill_dir.relative_to(root)),
        "evaluated_stage": stage,
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "evaluation": evaluation,
        "exception_usage": exception_usage,
        "policy_trace": trace,
    }
