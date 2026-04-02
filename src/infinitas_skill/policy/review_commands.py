"""Command helpers for review status and reviewer recommendation flows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from infinitas_skill.policy.reviewer_rotation import (
    recommend_reviewers,
    render_reviewer_recommendations,
)
from infinitas_skill.policy.reviews import (
    ROOT,
    ReviewPolicyError,
    evaluate_review_state,
    resolve_skill,
)


def print_csv_list(name, values):
    return f"{name}: {', '.join(values) if values else '-'}"


def configure_recommend_reviewers_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("skill")
    parser.add_argument("--as-active", action="store_true")
    parser.add_argument("--stage")
    parser.add_argument("--json", action="store_true")
    return parser


def build_recommend_reviewers_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Recommend reviewers and escalation paths for one skill"
    )
    return configure_recommend_reviewers_parser(parser)


def parse_recommend_reviewers_args(
    argv: list[str] | None = None,
    *,
    prog: str | None = None,
) -> argparse.Namespace:
    return build_recommend_reviewers_parser(prog=prog).parse_args(argv)


def configure_review_status_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.usage = (
        "infinitas policy review-status <skill-name-or-path> [--require-pass] "
        "[--as-active] [--stage STAGE] [--json] [--show-recommendations]"
    )
    parser.add_argument("skill")
    parser.add_argument("--require-pass", action="store_true")
    parser.add_argument("--as-active", action="store_true")
    parser.add_argument("--stage")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--show-recommendations", action="store_true")
    return parser


def build_review_status_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Show review gate status for one skill",
    )
    return configure_review_status_parser(parser)


def parse_review_status_args(
    argv: list[str] | None = None,
    *,
    prog: str | None = None,
) -> argparse.Namespace:
    return build_review_status_parser(prog=prog).parse_args(argv)


def build_reviewer_recommendation_payload(
    skill: str,
    *,
    root: Path = ROOT,
    stage: str | None = None,
    as_active: bool = False,
):
    if as_active and stage:
        raise ValueError("--as-active and --stage cannot be combined")
    skill_dir = resolve_skill(root, skill)
    return recommend_reviewers(skill_dir, root=root, stage=stage, as_active=as_active)


def recommend_reviewers_main(argv: list[str] | None = None) -> int:
    args = parse_recommend_reviewers_args(argv)
    if args.as_active and args.stage:
        print("--as-active and --stage cannot be combined", file=sys.stderr)
        return 1

    try:
        payload = build_reviewer_recommendation_payload(
            args.skill,
            root=ROOT,
            stage=args.stage,
            as_active=args.as_active,
        )
    except ReviewPolicyError as exc:
        for error in exc.errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_reviewer_recommendations(payload))
    return 0


def render_review_status(evaluation, recommendations=None) -> str:
    lines = [
        f"skill: {evaluation['skill']}@{evaluation['version']}",
        f"actual_stage: {evaluation['actual_stage']}",
        f"evaluated_stage: {evaluation['evaluated_stage']}",
        f"risk: {evaluation['risk_level']}",
        f"owner: {evaluation['owner']}",
        f"declared_review_state: {evaluation['declared_review_state']}",
        f"effective_review_state: {evaluation['effective_review_state']}",
        f"review_requests: {evaluation['review_request_count']}",
        f"required_approvals: {evaluation['required_approvals']}",
        f"approval_count: {evaluation['approval_count']}",
        f"rejection_count: {evaluation['rejection_count']}",
        f"blocking_rejections: {evaluation['blocking_rejection_count']}",
        f"quorum_met: {'yes' if evaluation['quorum_met'] else 'no'}",
        f"review_gate_pass: {'yes' if evaluation['review_gate_pass'] else 'no'}",
        print_csv_list("required_groups", evaluation["required_groups"]),
        print_csv_list("covered_groups", evaluation["covered_groups"]),
        print_csv_list("missing_groups", evaluation["missing_groups"]),
        f"ignored_decisions: {len(evaluation['ignored_decisions'])}",
    ]
    if evaluation["latest_decisions"]:
        lines.append("latest_decisions:")
        for item in evaluation["latest_decisions"]:
            reasons = f" [{'; '.join(item['reasons'])}]" if item["reasons"] else ""
            groups = ",".join(item["groups"]) if item["groups"] else "-"
            counted = "yes" if item["counted"] else "no"
            lines.append(
                f"- {item['reviewer']}: {item['decision']} counted={counted} "
                f"groups={groups} at={item['at']}{reasons}"
            )
    if recommendations is not None:
        lines.append(render_reviewer_recommendations(recommendations))
    return "\n".join(lines)


def review_status_main(argv: list[str] | None = None) -> int:
    args = parse_review_status_args(argv)
    if args.as_active and args.stage is not None:
        print("--as-active and --stage cannot be combined", file=sys.stderr)
        return 1

    skill_dir = resolve_skill(ROOT, args.skill)
    try:
        evaluation = evaluate_review_state(
            skill_dir,
            root=ROOT,
            stage=args.stage,
            as_active=args.as_active,
        )
        recommendations = (
            recommend_reviewers(
                skill_dir,
                root=ROOT,
                stage=args.stage,
                as_active=args.as_active,
            )
            if args.show_recommendations
            else None
        )
    except ReviewPolicyError as exc:
        for error in exc.errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    if args.json:
        payload = dict(evaluation)
        if recommendations is not None:
            payload["recommendations"] = recommendations
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.require_pass and not evaluation["review_gate_pass"]:
            return 1
        return 0

    print(render_review_status(evaluation, recommendations=recommendations))
    if args.require_pass and not evaluation["review_gate_pass"]:
        return 1
    return 0


__all__ = [
    "ROOT",
    "build_reviewer_recommendation_payload",
    "build_recommend_reviewers_parser",
    "build_review_status_parser",
    "configure_recommend_reviewers_parser",
    "configure_review_status_parser",
    "parse_recommend_reviewers_args",
    "parse_review_status_args",
    "print_csv_list",
    "recommend_reviewers_main",
    "render_review_status",
    "review_status_main",
]
