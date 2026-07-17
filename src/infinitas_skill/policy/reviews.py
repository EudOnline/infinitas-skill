"""Review policy evaluation for package-native promotion and release flows."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.root import ROOT

from .policy_pack import PolicyPackError, load_effective_policy_domain
from .primitives import normalize_string_list, parse_timestamp, unique_strings
from .review_evidence import load_review_evidence
from .team_policy import TeamPolicyError, expand_team_refs, load_team_policy

ALLOWED_DECISIONS = {"approved", "rejected"}
ALLOWED_REVIEW_STATES = {"draft", "under-review", "approved", "rejected"}
ALLOWED_RISK = {"low", "medium", "high"}
ALLOWED_STAGE = {"incubating", "active", "archived"}
GROUP_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MIN_TIME = datetime(1970, 1, 1, tzinfo=timezone.utc)

JsonDict = dict[str, Any]


class ReviewPolicyError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("invalid promotion policy")
        self.errors = errors


def normalize_team_list(values: object) -> list[str]:
    return normalize_string_list(values)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_skill(root: Path, arg: str) -> Path:
    direct = Path(arg)
    if direct.is_dir() and (direct / "_meta.json").exists():
        return direct.resolve()
    if not direct.is_absolute():
        repo_relative = (root / direct).resolve()
        if repo_relative.is_dir() and (repo_relative / "_meta.json").exists():
            return repo_relative
    for stage in ["incubating", "active", "archived"]:
        candidate = root / "skills" / stage / arg
        if candidate.is_dir() and (candidate / "_meta.json").exists():
            return candidate.resolve()
    raise SystemExit(f"cannot resolve skill: {arg}")


def load_meta(skill_dir: Path) -> JsonDict:
    return load_json(skill_dir / "_meta.json")


def load_reviews(skill_dir: Path) -> JsonDict:
    path = skill_dir / "reviews.json"
    if path.exists():
        payload = load_json(path)
    else:
        payload = {"version": 1, "requests": [], "entries": []}
    if not isinstance(payload, dict):
        payload = {"version": 1, "requests": [], "entries": []}
    if not isinstance(payload.get("version"), int):
        payload["version"] = 1
    if not isinstance(payload.get("requests"), list):
        payload["requests"] = []
    if not isinstance(payload.get("entries"), list):
        payload["entries"] = []
    return payload


def normalize_groups(
    raw_groups: object, root: Path = ROOT
) -> tuple[dict[str, JsonDict], list[str]]:
    errors: list[str] = []
    normalized: dict[str, Any] = {}
    if raw_groups is None:
        return normalized, errors
    if not isinstance(raw_groups, dict):
        return {}, ["reviews.groups must be an object"]
    try:
        team_policy = load_team_policy(root)
    except TeamPolicyError as exc:
        return {}, list(exc.errors)
    for group_name, raw_group in raw_groups.items():
        if not isinstance(group_name, str) or not GROUP_NAME_RE.match(group_name):
            errors.append(f"reviews.groups contains invalid group name {group_name!r}")
            continue
        description = None
        teams = []
        if isinstance(raw_group, list):
            members = raw_group
        elif isinstance(raw_group, dict):
            members = raw_group.get("members", [])
            teams = raw_group.get("teams", [])
            description = raw_group.get("description")
            unknown = sorted(set(raw_group) - {"members", "teams", "description"})
            if unknown:
                errors.append(
                    f"reviews.groups.{group_name} has unsupported keys: {', '.join(unknown)}"
                )
        else:
            errors.append(f"reviews.groups.{group_name} must be an array or object")
            continue
        if not isinstance(members, list) or not all(
            isinstance(item, str) and item.strip() for item in members
        ):
            errors.append(
                f"reviews.groups.{group_name}.members must be an array of non-empty strings"
            )
            members = []
        if not isinstance(teams, list) or not all(
            isinstance(item, str) and item.strip() for item in teams
        ):
            errors.append(
                f"reviews.groups.{group_name}.teams must be an array of non-empty strings"
            )
            teams = []
        if description is not None and not isinstance(description, str):
            errors.append(f"reviews.groups.{group_name}.description must be a string when present")
            description = None
        team_members = expand_team_refs(normalize_team_list(teams), team_policy)
        for missing_team in team_members.get("missing_teams", []):
            errors.append(
                f"reviews.groups.{group_name}.teams references unknown team {missing_team!r}"
            )
        direct_members = unique_strings(
            [item.strip() for item in members if isinstance(item, str) and item.strip()]
        )
        normalized[group_name] = {
            "members": direct_members,
            "teams": normalize_team_list(teams),
            "resolved_members": unique_strings(direct_members + team_members.get("actors", [])),
            "description": description.strip()
            if isinstance(description, str) and description.strip()
            else None,
        }
    return normalized, errors


def normalize_quorum_rule(path: str, raw_rule: object) -> tuple[JsonDict, list[str]]:
    errors: list[str] = []
    normalized: dict[str, Any] = {}
    if raw_rule is None:
        return normalized, errors
    if not isinstance(raw_rule, dict):
        return {}, [f"{path} must be an object"]
    unknown = sorted(set(raw_rule) - {"min_approvals", "required_groups"})
    if unknown:
        errors.append(f"{path} has unsupported keys: {', '.join(unknown)}")
    if "min_approvals" in raw_rule:
        min_approvals = raw_rule.get("min_approvals")
        if not isinstance(min_approvals, int) or min_approvals < 0:
            errors.append(f"{path}.min_approvals must be a non-negative integer")
        else:
            normalized["min_approvals"] = min_approvals
    if "required_groups" in raw_rule:
        required_groups = raw_rule.get("required_groups")
        if not isinstance(required_groups, list) or not all(
            isinstance(item, str) and item.strip() for item in required_groups
        ):
            errors.append(f"{path}.required_groups must be an array of non-empty strings")
        else:
            normalized["required_groups"] = unique_strings(
                [item.strip() for item in required_groups]
            )
    return normalized, errors


def _normalize_named_overrides(
    raw_quorum: JsonDict,
    *,
    field: str,
    allowed_names: set[str],
    invalid_label: str,
) -> tuple[dict[str, JsonDict], list[str]]:
    path = f"reviews.quorum.{field}"
    raw_overrides = raw_quorum.get(field, {})
    if not isinstance(raw_overrides, dict):
        return {}, [f"{path} must be an object"]
    normalized: dict[str, JsonDict] = {}
    errors: list[str] = []
    for name, raw_rule in raw_overrides.items():
        if name not in allowed_names:
            errors.append(f"{path} contains invalid {invalid_label} {name!r}")
            continue
        rule, rule_errors = normalize_quorum_rule(f"{path}.{name}", raw_rule)
        normalized[name] = rule
        errors.extend(rule_errors)
    return normalized, errors


def _normalize_stage_risk_overrides(
    raw_quorum: JsonDict,
) -> tuple[dict[str, dict[str, JsonDict]], list[str]]:
    path = "reviews.quorum.stage_risk_overrides"
    raw_overrides = raw_quorum.get("stage_risk_overrides", {})
    if not isinstance(raw_overrides, dict):
        return {}, [f"{path} must be an object"]
    normalized: dict[str, dict[str, JsonDict]] = {}
    errors: list[str] = []
    for stage, raw_risk_map in raw_overrides.items():
        if stage not in ALLOWED_STAGE:
            errors.append(f"{path} contains invalid stage {stage!r}")
            continue
        if not isinstance(raw_risk_map, dict):
            errors.append(f"{path}.{stage} must be an object")
            continue
        normalized[stage] = {}
        for risk_level, raw_rule in raw_risk_map.items():
            if risk_level not in ALLOWED_RISK:
                errors.append(f"{path}.{stage} contains invalid risk level {risk_level!r}")
                continue
            rule, rule_errors = normalize_quorum_rule(f"{path}.{stage}.{risk_level}", raw_rule)
            normalized[stage][risk_level] = rule
            errors.extend(rule_errors)
    return normalized, errors


def normalize_quorum(reviews_cfg: JsonDict) -> tuple[JsonDict, list[str]]:
    errors: list[str] = []
    normalized: dict[str, Any] = {
        "defaults": {},
        "stage_overrides": {},
        "risk_overrides": {},
        "stage_risk_overrides": {},
    }

    if "default_min_approvals" in reviews_cfg:
        default_min = reviews_cfg.get("default_min_approvals")
        if not isinstance(default_min, int) or default_min < 0:
            errors.append("reviews.default_min_approvals must be a non-negative integer")
        else:
            normalized["defaults"]["min_approvals"] = default_min

    raw_quorum = reviews_cfg.get("quorum")
    if raw_quorum is None:
        return normalized, errors
    if not isinstance(raw_quorum, dict):
        errors.append("reviews.quorum must be an object when present")
        return normalized, errors

    defaults, default_errors = normalize_quorum_rule(
        "reviews.quorum.defaults", raw_quorum.get("defaults", {})
    )
    normalized["defaults"].update(defaults)
    errors.extend(default_errors)

    for field, allowed_names, invalid_label in [
        ("stage_overrides", ALLOWED_STAGE, "stage"),
        ("risk_overrides", ALLOWED_RISK, "risk level"),
    ]:
        overrides, override_errors = _normalize_named_overrides(
            raw_quorum,
            field=field,
            allowed_names=allowed_names,
            invalid_label=invalid_label,
        )
        normalized[field] = overrides
        errors.extend(override_errors)
    stage_risk_overrides, stage_risk_errors = _normalize_stage_risk_overrides(raw_quorum)
    normalized["stage_risk_overrides"] = stage_risk_overrides
    errors.extend(stage_risk_errors)

    return normalized, errors


def configured_reviewers(
    policy: object, root: Path = ROOT
) -> tuple[dict[str, JsonDict], dict[str, JsonDict]]:
    reviews_cfg = policy.get("reviews", {}) if isinstance(policy, dict) else {}
    groups, group_errors = normalize_groups(reviews_cfg.get("groups", {}), root=root)
    if group_errors:
        raise ReviewPolicyError(group_errors)
    reviewers: dict[str, dict[str, Any]] = {}
    for group_name, group_data in groups.items():
        for reviewer in group_data.get("resolved_members", []):
            reviewers.setdefault(reviewer, {"groups": []})["groups"].append(group_name)
    for reviewer_data in reviewers.values():
        reviewer_data["groups"] = unique_strings(reviewer_data.get("groups", []))
    return groups, reviewers


def effective_quorum_rule(policy: object, stage: str, risk_level: str) -> JsonDict:
    reviews_cfg = policy.get("reviews", {}) if isinstance(policy, dict) else {}
    quorum, _ = normalize_quorum(reviews_cfg)
    rule = {"min_approvals": 0, "required_groups": []}

    def apply(raw_rule: JsonDict) -> None:
        if "min_approvals" in raw_rule:
            rule["min_approvals"] = raw_rule["min_approvals"]
        if "required_groups" in raw_rule:
            rule["required_groups"] = unique_strings(raw_rule["required_groups"])

    apply(quorum.get("defaults", {}))
    apply(quorum.get("stage_overrides", {}).get(stage, {}))
    apply(quorum.get("risk_overrides", {}).get(risk_level, {}))
    apply(quorum.get("stage_risk_overrides", {}).get(stage, {}).get(risk_level, {}))
    return rule


def owner_review_unavoidable(
    owner: str | None,
    reviewers: dict[str, JsonDict] | None,
    required_groups: list[str],
    min_approvals: int,
) -> bool:
    if not owner:
        return False
    non_owner_reviewers = {
        reviewer: data for reviewer, data in (reviewers or {}).items() if reviewer != owner
    }
    if len(non_owner_reviewers) < (min_approvals or 0):
        return True
    if required_groups:
        covered_groups: set[str] = set()
        for reviewer_data in non_owner_reviewers.values():
            covered_groups.update(reviewer_data.get("groups", []))
        if any(group_name not in covered_groups for group_name in required_groups):
            return True
    return False


def validate_promotion_policy(policy: object, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if not isinstance(policy, dict):
        return ["promotion policy must be a JSON object"]
    if "version" in policy:
        version = policy.get("version")
        if not isinstance(version, int) or version < 1:
            errors.append("version must be a positive integer")

    errors.extend(_validate_active_requires(policy.get("active_requires")))

    reviews_cfg = policy.get("reviews")
    if not isinstance(reviews_cfg, dict):
        errors.append("reviews must be an object")
        return errors
    errors.extend(_validate_review_flags(reviews_cfg))

    groups, group_errors = normalize_groups(reviews_cfg.get("groups", {}), root=root)
    errors.extend(group_errors)
    quorum, quorum_errors = normalize_quorum(reviews_cfg)
    errors.extend(quorum_errors)

    errors.extend(_validate_quorum_group_refs(groups, quorum))
    errors.extend(_validate_high_risk(policy.get("high_risk_active_requires", {})))
    return errors


def _validate_active_requires(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["active_requires must be an object"]
    errors: list[str] = []
    review_states = value.get("review_state", [])
    if not isinstance(review_states, list) or not review_states:
        errors.append("active_requires.review_state must be a non-empty array")
    elif any(state not in ALLOWED_REVIEW_STATES for state in review_states):
        errors.append(
            f"active_requires.review_state must contain only {sorted(ALLOWED_REVIEW_STATES)}"
        )
    for key in ["require_changelog", "require_smoke_test", "require_owner"]:
        if key in value and not isinstance(value.get(key), bool):
            errors.append(f"active_requires.{key} must be boolean when present")
    return errors


def _validate_review_flags(reviews_cfg: JsonDict) -> list[str]:
    keys = [
        "require_reviews_file",
        "reviewer_must_differ_from_owner",
        "allow_owner_when_no_distinct_reviewer",
        "block_on_rejection",
    ]
    return [
        f"reviews.{key} must be boolean when present"
        for key in keys
        if key in reviews_cfg and not isinstance(reviews_cfg.get(key), bool)
    ]


def _validate_quorum_group_refs(groups: JsonDict, quorum: JsonDict) -> list[str]:
    rules: list[tuple[str, JsonDict]] = [
        ("reviews.quorum.defaults", quorum.get("defaults", {})),
    ]
    rules.extend(
        (f"reviews.quorum.stage_overrides.{stage}", rule)
        for stage, rule in quorum.get("stage_overrides", {}).items()
    )
    rules.extend(
        (f"reviews.quorum.risk_overrides.{risk}", rule)
        for risk, rule in quorum.get("risk_overrides", {}).items()
    )
    for stage, risk_map in quorum.get("stage_risk_overrides", {}).items():
        rules.extend(
            (f"reviews.quorum.stage_risk_overrides.{stage}.{risk}", rule)
            for risk, rule in risk_map.items()
        )
    return [
        f"{path}.required_groups references unknown reviewer group {group_name!r}"
        for path, rule in rules
        for group_name in rule.get("required_groups", [])
        if group_name not in groups
    ]


def _validate_high_risk(value: object) -> list[str]:
    if value and not isinstance(value, dict):
        return ["high_risk_active_requires must be an object when present"]
    if not isinstance(value, dict):
        return []
    errors: list[str] = []
    min_maintainers = value.get("min_maintainers")
    if "min_maintainers" in value and (not isinstance(min_maintainers, int) or min_maintainers < 0):
        errors.append(
            "high_risk_active_requires.min_maintainers must be a non-negative integer when present"
        )
    if "require_requires_block" in value and not isinstance(
        value.get("require_requires_block"), bool
    ):
        errors.append(
            "high_risk_active_requires.require_requires_block must be boolean when present"
        )
    return errors


def load_promotion_policy(root: Path = ROOT) -> JsonDict:
    try:
        policy = load_effective_policy_domain(root, "promotion_policy")
    except PolicyPackError as exc:
        raise ReviewPolicyError(exc.errors) from exc
    errors = validate_promotion_policy(policy, root=root)
    if errors:
        raise ReviewPolicyError(errors)
    return policy


def latest_distinct_entries(entries: object) -> dict[str, JsonDict]:
    latest: dict[str, tuple[tuple[datetime, int], dict[str, Any]]] = {}
    raw_entries = entries if isinstance(entries, list) else []
    for index, raw_entry in enumerate(raw_entries):
        if not isinstance(raw_entry, dict):
            continue
        reviewer = raw_entry.get("reviewer")
        if not isinstance(reviewer, str) or not reviewer.strip():
            continue
        timestamp = parse_timestamp(raw_entry.get("at")) or MIN_TIME
        rank = (timestamp, index)
        stored = latest.get(reviewer)
        if stored is None or rank >= stored[0]:
            latest[reviewer] = (rank, dict(raw_entry))
    return {reviewer: entry for reviewer, (_, entry) in sorted(latest.items())}


def review_decision_entries(skill_dir: Path) -> tuple[JsonDict, list[JsonDict]]:
    reviews = load_reviews(skill_dir)
    entries: list[JsonDict] = []
    for raw_entry in reviews.get("entries", []):
        if not isinstance(raw_entry, dict):
            continue
        entry = dict(raw_entry)
        entry.setdefault("source", "reviews.json")
        entry.setdefault("source_kind", "repo-review")
        entry.setdefault("source_ref", "reviews.json")
        entry.setdefault("url", None)
        entries.append(entry)

    evidence = load_review_evidence(skill_dir)
    for raw_entry in evidence.get("entries", []):
        entry = dict(raw_entry)
        entry.setdefault("note", None)
        entries.append(entry)

    return reviews, entries
