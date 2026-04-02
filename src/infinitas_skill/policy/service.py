"""Policy validation and promotion commands wired into the unified infinitas CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from infinitas_skill.policy.exception_policy import (
    ExceptionPolicyError,
    load_exception_policy,
    match_active_exceptions,
)
from infinitas_skill.policy.policy_pack import PolicyPackError, load_policy_domain_resolution
from infinitas_skill.policy.reviews import (
    ReviewPolicyError,
    evaluate_review_state,
    load_promotion_policy,
)
from infinitas_skill.policy.trace import build_policy_trace, render_policy_trace
from infinitas_skill.root import ROOT

POLICY_TOP_LEVEL_HELP = "Policy validation and promotion tools"
POLICY_PARSER_DESCRIPTION = "Policy validation and promotion CLI"

SUPPORTED_DOMAINS = {
    "promotion_policy",
    "namespace_policy",
    "signing",
    "registry_sources",
    "team_policy",
    "exception_policy",
}
NAME_KEYS = {"$schema", "schema_version", "name", "description", "domains"}
SELECTOR_KEYS = {"$schema", "version", "description", "compatibility_version", "active_packs"}


def _rule(rule_text, *, id=None, value=None, **extra):
    item = {"rule": rule_text}
    if id is not None:
        item["id"] = id
    if value is not None:
        item["value"] = value
    for key, raw in extra.items():
        if raw is not None:
            item[key] = raw
    return item


def _load_json_object(path: Path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_policy_pack_selector(path: Path, payload):
    errors = []
    unknown = sorted(set(payload) - SELECTOR_KEYS)
    if unknown:
        errors.append(f"policy-pack selection has unsupported keys: {', '.join(unknown)}")
    if "$schema" in payload and not _is_nonempty_string(payload.get("$schema")):
        errors.append("policy-pack selection $schema must be a string when present")
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        errors.append("policy-pack selection version must be an integer >= 1")
    if "description" in payload and not isinstance(payload.get("description"), str):
        errors.append("policy-pack selection description must be a string when present")
    if "compatibility_version" in payload and not _is_nonempty_string(
        payload.get("compatibility_version")
    ):
        errors.append(
            "policy-pack selection compatibility_version must be a non-empty string when present"
        )
    active_packs = payload.get("active_packs")
    if not isinstance(active_packs, list) or not active_packs:
        errors.append("policy-pack selection active_packs must be a non-empty array")
        return errors, []
    clean_names = []
    seen = set()
    duplicates = []
    for item in active_packs:
        if not _is_nonempty_string(item):
            errors.append("policy-pack selection active_packs entries must be non-empty strings")
            continue
        name = item.strip()
        clean_names.append(name)
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        errors.append(f"duplicate active pack names: {', '.join(duplicates)}")
    return errors, clean_names


def validate_policy_pack(path: Path, expected_name: str, payload):
    errors = []
    unknown = sorted(set(payload) - NAME_KEYS)
    if unknown:
        errors.append(f"policy pack {expected_name!r} has unsupported keys: {', '.join(unknown)}")
    if "$schema" in payload and not _is_nonempty_string(payload.get("$schema")):
        errors.append(f"policy pack {expected_name!r} $schema must be a string when present")
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, int) or schema_version < 1:
        errors.append(f"policy pack {expected_name!r} schema_version must be an integer >= 1")
    name = payload.get("name")
    if not _is_nonempty_string(name):
        errors.append(f"policy pack {expected_name!r} name must be a non-empty string")
    elif name.strip() != expected_name:
        errors.append(f"policy pack {expected_name!r} name must match file stem, got {name!r}")
    if "description" in payload and not isinstance(payload.get("description"), str):
        errors.append(f"policy pack {expected_name!r} description must be a string when present")
    domains = payload.get("domains")
    if not isinstance(domains, dict) or not domains:
        errors.append(f"policy pack {expected_name!r} domains must be a non-empty object")
        return errors
    for domain_name, domain_payload in domains.items():
        if domain_name not in SUPPORTED_DOMAINS:
            errors.append(f"unknown policy domain {domain_name!r} in pack {expected_name!r}")
            continue
        if not isinstance(domain_payload, dict):
            errors.append(f"policy pack {expected_name!r} domain {domain_name!r} must be an object")
    return errors


def collect_skill_report(
    skill_dir: Path, *, as_active: bool = False, root: Path = ROOT, exception_policy=None
):
    skill_dir = Path(skill_dir).resolve()
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    stage = "active" if as_active else skill_dir.parent.name

    try:
        policy_resolution = load_policy_domain_resolution(root, "promotion_policy")
    except PolicyPackError as exc:
        raise ReviewPolicyError(exc.errors) from exc

    policy = policy_resolution["effective"]
    reviews_cfg = policy.get("reviews", {})
    req = policy.get("active_requires", {})
    issues = []

    def add_issue(rule_id, message, *, rule, value=None, next_action=None):
        issues.append(
            {
                "id": rule_id,
                "message": message,
                "rule": rule,
                "value": value,
                "next_action": next_action,
            }
        )

    if stage != "active":
        trace = build_policy_trace(
            domain="promotion_policy",
            decision="skipped",
            summary="promotion policy is enforced only for active-stage evaluation",
            effective_sources=policy_resolution.get("effective_sources"),
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

    evaluation = evaluate_review_state(skill_dir, root=root, stage="active", policy=policy)
    reviews_path = skill_dir / "reviews.json"

    if reviews_cfg.get("require_reviews_file") and not reviews_path.is_file():
        message = f"{skill_dir}: active skill requires reviews.json"
        add_issue(
            "missing-reviews-file",
            message,
            rule="reviews file is required for active skills",
            value="missing reviews.json",
            next_action="add reviews.json before promoting this skill",
        )
    if evaluation["approval_count"] < evaluation["required_approvals"]:
        message = f"{skill_dir}: active skill requires at least {evaluation['required_approvals']} counted approval(s)"
        add_issue(
            "minimum-approvals",
            message,
            rule="minimum counted approvals must be met",
            value=f"{evaluation['approval_count']}/{evaluation['required_approvals']}",
            next_action="collect the required number of counted approvals",
        )
    if evaluation["missing_groups"]:
        joined = ", ".join(evaluation["missing_groups"])
        message = f"{skill_dir}: active skill is missing reviewer group coverage for {joined}"
        add_issue(
            "required-reviewer-groups",
            message,
            rule="required reviewer groups must be covered",
            value=joined,
            next_action="request review from the missing reviewer groups",
        )
    if reviews_cfg.get("block_on_rejection", False) and evaluation["blocking_rejection_count"]:
        message = f"{skill_dir}: active skill has blocking rejection(s)"
        add_issue(
            "blocking-rejections",
            message,
            rule="blocking rejections must be resolved before promotion",
            value=evaluation["blocking_rejection_count"],
            next_action="resolve or supersede the blocking rejection decisions",
        )
    if not evaluation["review_gate_pass"] and not issues:
        message = f"{skill_dir}: active skill does not satisfy computed review quorum"
        add_issue(
            "review-quorum",
            message,
            rule="computed review quorum must pass",
            next_action="inspect the review quorum inputs and latest decisions",
        )

    if evaluation["effective_review_state"] not in req.get("review_state", []):
        message = f"{skill_dir}: review_state must be one of {req.get('review_state', [])}"
        add_issue(
            "effective-review-state",
            message,
            rule="effective review_state must be allowed for promotion",
            value=evaluation["effective_review_state"],
        )
    if req.get("require_changelog") and not (skill_dir / "CHANGELOG.md").is_file():
        message = f"{skill_dir}: active skill requires CHANGELOG.md"
        add_issue(
            "missing-changelog",
            message,
            rule="CHANGELOG.md is required for active promotion",
        )
    if req.get("require_smoke_test"):
        smoke = meta.get("tests", {}).get("smoke", "tests/smoke.md")
        if not (skill_dir / smoke).is_file():
            message = f"{skill_dir}: active skill requires smoke test {smoke}"
            add_issue(
                "missing-smoke-test",
                message,
                rule="smoke test file is required for active promotion",
                value=smoke,
            )
    if req.get("require_owner") and not meta.get("owner"):
        message = f"{skill_dir}: active skill requires owner"
        add_issue(
            "missing-owner",
            message,
            rule="owner metadata is required for active promotion",
        )

    high = (
        policy.get("high_risk_active_requires", {})
        if isinstance(policy.get("high_risk_active_requires"), dict)
        else {}
    )
    if meta.get("risk_level") == "high":
        maintainers = meta.get("maintainers", []) or []
        if len(maintainers) < high.get("min_maintainers", 0):
            message = f"{skill_dir}: high-risk active skill requires at least {high.get('min_maintainers', 0)} maintainer(s)"
            add_issue(
                "minimum-maintainers",
                message,
                rule="high-risk skills require minimum maintainer coverage",
                value=f"{len(maintainers)}/{high.get('min_maintainers', 0)}",
            )
        if high.get("require_requires_block") and not isinstance(meta.get("requires"), dict):
            message = f"{skill_dir}: high-risk active skill requires a requires block"
            add_issue(
                "missing-requires-block",
                message,
                rule="high-risk skills require a requires block",
            )

    if exception_policy is None:
        try:
            exception_policy = load_exception_policy(root)
        except ExceptionPolicyError as exc:
            raise ReviewPolicyError(exc.errors) from exc

    exception_usage = match_active_exceptions(
        "promotion",
        meta,
        [item["id"] for item in issues],
        root=root,
        policy=exception_policy,
    )
    waived_rule_ids = {
        matched_rule
        for item in exception_usage
        for matched_rule in item.get("matched_rules", [])
        if isinstance(matched_rule, str) and matched_rule
    }
    remaining_issues = [item for item in issues if item.get("id") not in waived_rule_ids]
    errors = [item["message"] for item in remaining_issues]
    blocking_rules = [
        _rule(item["rule"], id=item.get("id"), value=item.get("value"), message=item.get("message"))
        for item in remaining_issues
    ]
    next_actions = []
    for item in remaining_issues:
        action = item.get("next_action")
        if isinstance(action, str) and action and action not in next_actions:
            next_actions.append(action)

    trace = build_policy_trace(
        domain="promotion_policy",
        decision="allow" if not errors else "deny",
        summary="promotion policy passed for active skill"
        if not errors
        else f"promotion policy blocked by {len(errors)} issue(s)",
        effective_sources=policy_resolution.get("effective_sources"),
        applied_rules=[
            _rule(
                "active skill review_state must satisfy active_requires.review_state",
                id="effective-review-state",
                value=",".join(req.get("review_state", [])),
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
        blocking_rules=blocking_rules,
        reasons=[
            f"effective_review_state={evaluation.get('effective_review_state')}",
            f"approval_count={evaluation.get('approval_count')}",
            f"blocking_rejections={evaluation.get('blocking_rejection_count')}",
            f"exceptions_applied={len(exception_usage)}",
        ],
        next_actions=next_actions,
        exceptions=exception_usage,
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


def print_promotion_text_report(report, *, debug_policy=False):
    if report["errors"]:
        for message in report["errors"]:
            print(f"FAIL: {message}", file=sys.stderr)
        if debug_policy:
            print(render_policy_trace(report["policy_trace"]), file=sys.stderr)
        return
    print(f"OK: promotion policy passed for {ROOT / report['skill_path']}")
    if debug_policy:
        print(render_policy_trace(report["policy_trace"]))


def configure_check_policy_packs_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    return parser


def configure_check_promotion_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("targets", nargs="*", help="Skill directory path(s) to check")
    parser.add_argument(
        "--as-active", action="store_true", help="Evaluate targets as active-stage skills"
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    parser.add_argument(
        "--debug-policy", action="store_true", help="Print a human-readable policy trace"
    )
    return parser


def build_check_policy_packs_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate policy-pack selector and active pack files", prog=prog
    )
    return configure_check_policy_packs_parser(parser)


def build_check_promotion_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check active promotion policy for one or more skills", prog=prog
    )
    return configure_check_promotion_parser(parser)


def run_check_policy_packs(*, root: Path = ROOT) -> int:
    selector_path = root / "policy" / "policy-packs.json"
    try:
        selector = _load_json_object(selector_path)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    errors, active_packs = validate_policy_pack_selector(selector_path, selector)
    for pack_name in active_packs:
        pack_path = root / "policy" / "packs" / f"{pack_name}.json"
        if not pack_path.exists():
            errors.append(f"missing policy pack file: {pack_path}")
            continue
        try:
            payload = _load_json_object(pack_path)
        except Exception as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_policy_pack(pack_path, pack_name, payload))

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"OK: validated {len(active_packs)} policy pack(s)")
    return 0


def run_check_promotion(
    *,
    targets: list[str],
    as_active: bool = False,
    as_json: bool = False,
    debug_policy: bool = False,
    root: Path = ROOT,
) -> int:
    try:
        load_promotion_policy(root)
        exception_policy = load_exception_policy(root)
    except ReviewPolicyError as exc:
        for error in exc.errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    except ExceptionPolicyError as exc:
        for error in exc.errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    resolved_targets = [Path(path).resolve() for path in targets]
    if not resolved_targets:
        base = root / "skills" / "active"
        resolved_targets = (
            [path for path in base.iterdir() if path.is_dir() and (path / "_meta.json").exists()]
            if base.exists()
            else []
        )

    reports = [
        collect_skill_report(
            target, as_active=as_active, root=root, exception_policy=exception_policy
        )
        for target in resolved_targets
    ]
    error_count = sum(report["error_count"] for report in reports)

    if as_json:
        payload = (
            reports[0] if len(reports) == 1 else {"results": reports, "error_count": error_count}
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for report in reports:
            print_promotion_text_report(report, debug_policy=debug_policy)

    return 1 if error_count else 0


def configure_policy_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(
        dest="policy_command", metavar="{check-packs,check-promotion}"
    )

    check_packs = subparsers.add_parser(
        "check-packs",
        help="Validate policy-pack selector and active pack files",
        description="Validate policy-pack selector and active pack files",
    )
    configure_check_policy_packs_parser(check_packs)
    check_packs.set_defaults(_handler=lambda _args: run_check_policy_packs())

    check_promotion = subparsers.add_parser(
        "check-promotion",
        help="Check active promotion policy for one or more skills",
        description="Check active promotion policy for one or more skills",
    )
    configure_check_promotion_parser(check_promotion)
    check_promotion.set_defaults(
        _handler=lambda args: run_check_promotion(
            targets=args.targets,
            as_active=args.as_active,
            as_json=args.json,
            debug_policy=args.debug_policy,
        )
    )
    return parser


def build_policy_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=POLICY_PARSER_DESCRIPTION, prog=prog)
    return configure_policy_parser(parser)


def policy_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = build_policy_parser(prog=prog)
    args = parser.parse_args(argv)
    handler = getattr(args, "_handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


__all__ = [
    "POLICY_PARSER_DESCRIPTION",
    "POLICY_TOP_LEVEL_HELP",
    "build_check_policy_packs_parser",
    "build_check_promotion_parser",
    "build_policy_parser",
    "configure_check_policy_packs_parser",
    "configure_check_promotion_parser",
    "configure_policy_parser",
    "policy_main",
    "run_check_policy_packs",
    "run_check_promotion",
]
