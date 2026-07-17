"""Exception policy evaluation for package-native promotion and release checks."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.root import ROOT

from .policy_pack import PolicyPackError, load_policy_domain_resolution
from .primitives import normalize_string_list, unique_strings
from .skill_identity import normalize_skill_identity
from .team_policy import TeamPolicyError, expand_team_refs, load_team_policy

EXCEPTION_SCOPE_VALUES = {"promotion", "release"}
EXCEPTION_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ROOT_KEYS = {"$schema", "version", "exceptions"}
RECORD_KEYS = {
    "id",
    "scope",
    "skills",
    "rules",
    "approved_by",
    "approved_by_teams",
    "approved_at",
    "justification",
    "expires_at",
}

JsonDict = dict[str, Any]


class ExceptionPolicyError(Exception):
    def __init__(self, errors: str | Sequence[object]) -> None:
        if isinstance(errors, str):
            errors = [errors]
        self.errors = [str(item) for item in errors if str(item)]
        super().__init__("; ".join(self.errors))


def _normalize_string_list(values: object) -> list[str]:
    return normalize_string_list(values)


def _parse_timestamp(
    field_name: str, value: object, *, errors: list[str]
) -> tuple[str | None, datetime | None]:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field_name} must be a non-empty string")
        return None, None
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{field_name} must be an ISO-8601 timestamp")
        return text, None
    if parsed.tzinfo is None:
        errors.append(f"{field_name} must include an explicit timezone")
        return text, None
    return text, parsed.astimezone(timezone.utc)


def expand_exception_approvers(record: JsonDict, team_policy: JsonDict) -> JsonDict:
    approved_by = _normalize_string_list(record.get("approved_by"))
    approved_by_teams = _normalize_string_list(record.get("approved_by_teams"))
    team_report = expand_team_refs(approved_by_teams, team_policy)
    return {
        "approved_by": approved_by,
        "approved_by_teams": approved_by_teams,
        "resolved_approved_by": unique_strings(approved_by + list(team_report.get("actors", []))),
        "missing_approved_by_teams": list(team_report.get("missing_teams", [])),
    }


def _validate_policy_root(payload: JsonDict, errors: list[str]) -> list[object]:
    unknown_root = sorted(set(payload) - ROOT_KEYS)
    if unknown_root:
        errors.append(f"exception-policy has unsupported keys: {', '.join(unknown_root)}")
    if "$schema" in payload and not isinstance(payload.get("$schema"), str):
        errors.append("exception-policy $schema must be a string when present")
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        errors.append("exception-policy version must be an integer >= 1")

    raw_exceptions = payload.get("exceptions", [])
    if not isinstance(raw_exceptions, list):
        errors.append("exception-policy exceptions must be an array")
        return []
    return raw_exceptions


def _validate_exact_targets(
    raw_record: JsonDict, label: str, field: str, errors: list[str]
) -> list[str]:
    values = _normalize_string_list(raw_record.get(field))
    if raw_record.get(field) is not None and not isinstance(raw_record.get(field), list):
        errors.append(f"{label}.{field} must be an array")
    if not values:
        requirement = (
            "at least one exact skill name or qualified name"
            if field == "skills"
            else "at least one stable rule id"
        )
        errors.append(f"{label}.{field} must include {requirement}")
    if any("*" in item or "?" in item for item in values):
        target = "names" if field == "skills" else "rule ids"
        errors.append(f"{label}.{field} must use exact {target} only; wildcards are not supported")
    return values


def _validate_record_identity(
    raw_record: JsonDict, label: str, seen_ids: set[str], errors: list[str]
) -> tuple[str | None, object]:
    record_id = raw_record.get("id")
    if not isinstance(record_id, str) or not EXCEPTION_ID_RE.match(record_id.strip()):
        errors.append(f"{label}.id must be a lowercase slug")
        record_id = None
    else:
        record_id = record_id.strip()
        if record_id in seen_ids:
            errors.append(f"{label}.id {record_id!r} is duplicated")
        seen_ids.add(record_id)
    scope = raw_record.get("scope")
    if scope not in EXCEPTION_SCOPE_VALUES:
        errors.append(f"{label}.scope must be one of {sorted(EXCEPTION_SCOPE_VALUES)!r}")
    return record_id, scope


def _validate_record_approvers(
    raw_record: JsonDict, label: str, team_policy: JsonDict, errors: list[str]
) -> JsonDict:
    approvers = expand_exception_approvers(raw_record, team_policy)
    for field in ("approved_by", "approved_by_teams"):
        if raw_record.get(field) is not None and not isinstance(raw_record.get(field), list):
            errors.append(f"{label}.{field} must be an array when present")
    for missing_team in approvers.get("missing_approved_by_teams", []):
        errors.append(f"{label}.approved_by_teams references unknown team {missing_team!r}")
    if not approvers.get("resolved_approved_by"):
        errors.append(
            f"{label} must resolve at least one approver via approved_by or approved_by_teams"
        )
    return approvers


def _validate_exception_record(
    raw_record: object, index: int, team_policy: JsonDict, seen_ids: set[str]
) -> tuple[list[str], JsonDict | None]:
    label = f"exception-policy exceptions[{index}]"
    if not isinstance(raw_record, dict):
        return [f"{label} must be an object"], None
    errors: list[str] = []
    unknown = sorted(set(raw_record) - RECORD_KEYS)
    if unknown:
        errors.append(f"{label} has unsupported keys: {', '.join(unknown)}")
    record_id, scope = _validate_record_identity(raw_record, label, seen_ids, errors)
    skills = _validate_exact_targets(raw_record, label, "skills", errors)
    rules = _validate_exact_targets(raw_record, label, "rules", errors)
    approvers = _validate_record_approvers(raw_record, label, team_policy, errors)
    approved_at, approved_at_dt = _parse_timestamp(
        f"{label}.approved_at", raw_record.get("approved_at"), errors=errors
    )
    expires_at, expires_at_dt = _parse_timestamp(
        f"{label}.expires_at", raw_record.get("expires_at"), errors=errors
    )
    if approved_at_dt and expires_at_dt and expires_at_dt <= approved_at_dt:
        errors.append(f"{label}.expires_at must be later than approved_at")
    justification = raw_record.get("justification")
    if not isinstance(justification, str) or not justification.strip():
        errors.append(f"{label}.justification must be a non-empty string")
        justification = None
    else:
        justification = justification.strip()
    if errors:
        return errors, None
    return [], {
        "id": record_id,
        "scope": scope,
        "skills": skills,
        "rules": rules,
        "approved_by": approvers.get("approved_by", []),
        "approved_by_teams": approvers.get("approved_by_teams", []),
        "resolved_approved_by": approvers.get("resolved_approved_by", []),
        "approved_at": approved_at,
        "approved_at_dt": approved_at_dt,
        "justification": justification,
        "expires_at": expires_at,
        "expires_at_dt": expires_at_dt,
    }


def validate_exception_policy(
    payload: object, team_policy: JsonDict
) -> tuple[list[str], list[JsonDict]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["exception-policy must be a JSON object"], []
    raw_exceptions = _validate_policy_root(payload, errors)

    normalized: list[JsonDict] = []
    seen_ids: set[str] = set()
    for index, raw_record in enumerate(raw_exceptions, start=1):
        record_errors, record = _validate_exception_record(raw_record, index, team_policy, seen_ids)
        if record_errors:
            errors.extend(record_errors)
            continue
        if record is not None:
            normalized.append(record)

    return errors, normalized


def load_exception_policy(root: str | Path = ROOT) -> JsonDict:
    root = Path(root).resolve()
    path = root / "policy" / "exception-policy.json"

    try:
        team_policy = load_team_policy(root)
    except TeamPolicyError as exc:
        raise ExceptionPolicyError(exc.errors) from exc

    try:
        resolution = load_policy_domain_resolution(root, "exception_policy")
    except PolicyPackError as exc:
        missing = "missing policy source for domain 'exception_policy'"
        if exc.errors and all(error.startswith(missing) for error in exc.errors):
            return {
                "path": path,
                "version": 1,
                "exceptions": [],
                "effective_sources": [],
                "team_policy": team_policy,
            }
        raise ExceptionPolicyError(exc.errors) from exc

    payload = resolution.get("effective") or {}
    errors, exceptions = validate_exception_policy(payload, team_policy)
    if errors:
        raise ExceptionPolicyError(errors)
    return {
        "path": path,
        "version": payload.get("version"),
        "exceptions": exceptions,
        "effective_sources": resolution.get("effective_sources", []),
        "team_policy": team_policy,
    }


def _matches_skill_target(targets: object, identity: object) -> bool:
    identity = identity if isinstance(identity, dict) else {}
    qualified = identity.get("qualified_name")
    name = identity.get("name")
    for target in _normalize_string_list(targets):
        if "/" in target:
            if target == qualified:
                return True
        elif target == name:
            return True
    return False


def match_active_exceptions(
    scope: str | None,
    skill_identity: object,
    blocking_rule_ids: object,
    root: str | Path = ROOT,
    policy: JsonDict | None = None,
) -> list[JsonDict]:
    scope = (scope or "").strip()
    if scope not in EXCEPTION_SCOPE_VALUES:
        return []

    requested_rules = _normalize_string_list(blocking_rule_ids)
    if not requested_rules:
        return []

    if policy is None:
        policy = load_exception_policy(root)

    identity = normalize_skill_identity(skill_identity) if isinstance(skill_identity, dict) else {}
    now = datetime.now(timezone.utc)
    usage: list[JsonDict] = []
    for record in policy.get("exceptions") or []:
        if record.get("scope") != scope:
            continue
        if not _matches_skill_target(record.get("skills"), identity):
            continue
        approved_at_dt = record.get("approved_at_dt")
        expires_at_dt = record.get("expires_at_dt")
        if not approved_at_dt or not expires_at_dt or approved_at_dt > now or expires_at_dt <= now:
            continue
        matched_rules = [rule for rule in requested_rules if rule in (record.get("rules") or [])]
        if not matched_rules:
            continue
        usage.append(
            {
                "id": record.get("id"),
                "scope": record.get("scope"),
                "matched_rules": matched_rules,
                "skills": list(record.get("skills") or []),
                "approved_by": list(record.get("resolved_approved_by") or []),
                "approved_at": record.get("approved_at"),
                "expires_at": record.get("expires_at"),
                "justification": record.get("justification"),
            }
        )
    return usage
