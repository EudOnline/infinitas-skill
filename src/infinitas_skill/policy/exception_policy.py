"""Exception policy evaluation for package-native promotion and release checks."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from infinitas_skill.root import ROOT

from .policy_pack import PolicyPackError, load_policy_domain_resolution
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


class ExceptionPolicyError(Exception):
    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = [str(item) for item in errors if str(item)]
        super().__init__("; ".join(self.errors))


def _unique_strings(values):
    seen = set()
    result = []
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalize_string_list(values):
    if values is None:
        return []
    if not isinstance(values, list):
        return []
    return _unique_strings(
        [item.strip() for item in values if isinstance(item, str) and item.strip()]
    )


def _parse_timestamp(field_name, value, *, errors):
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


def expand_exception_approvers(record, team_policy):
    approved_by = _normalize_string_list(record.get("approved_by"))
    approved_by_teams = _normalize_string_list(record.get("approved_by_teams"))
    team_report = expand_team_refs(approved_by_teams, team_policy)
    return {
        "approved_by": approved_by,
        "approved_by_teams": approved_by_teams,
        "resolved_approved_by": _unique_strings(approved_by + list(team_report.get("actors", []))),
        "missing_approved_by_teams": list(team_report.get("missing_teams", [])),
    }


def validate_exception_policy(payload, team_policy):
    errors = []
    if not isinstance(payload, dict):
        return ["exception-policy must be a JSON object"], []

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
        raw_exceptions = []

    normalized = []
    seen_ids = set()
    for index, raw_record in enumerate(raw_exceptions, start=1):
        label = f"exception-policy exceptions[{index}]"
        if not isinstance(raw_record, dict):
            errors.append(f"{label} must be an object")
            continue

        unknown = sorted(set(raw_record) - RECORD_KEYS)
        if unknown:
            errors.append(f"{label} has unsupported keys: {', '.join(unknown)}")

        record_errors = []
        record_id = raw_record.get("id")
        if not isinstance(record_id, str) or not EXCEPTION_ID_RE.match(record_id.strip()):
            record_errors.append(f"{label}.id must be a lowercase slug")
            record_id = None
        else:
            record_id = record_id.strip()
            if record_id in seen_ids:
                record_errors.append(f"{label}.id {record_id!r} is duplicated")
            seen_ids.add(record_id)

        scope = raw_record.get("scope")
        if scope not in EXCEPTION_SCOPE_VALUES:
            record_errors.append(f"{label}.scope must be one of {sorted(EXCEPTION_SCOPE_VALUES)!r}")

        skills = _normalize_string_list(raw_record.get("skills"))
        if raw_record.get("skills") is not None and not isinstance(raw_record.get("skills"), list):
            record_errors.append(f"{label}.skills must be an array")
        if not skills:
            record_errors.append(
                f"{label}.skills must include at least one exact skill name or qualified name"
            )
        if any("*" in item or "?" in item for item in skills):
            record_errors.append(
                f"{label}.skills must use exact names only; wildcards are not supported"
            )

        rules = _normalize_string_list(raw_record.get("rules"))
        if raw_record.get("rules") is not None and not isinstance(raw_record.get("rules"), list):
            record_errors.append(f"{label}.rules must be an array")
        if not rules:
            record_errors.append(f"{label}.rules must include at least one stable rule id")
        if any("*" in item or "?" in item for item in rules):
            record_errors.append(
                f"{label}.rules must use exact rule ids only; wildcards are not supported"
            )

        approvers = expand_exception_approvers(raw_record, team_policy)
        if raw_record.get("approved_by") is not None and not isinstance(
            raw_record.get("approved_by"), list
        ):
            record_errors.append(f"{label}.approved_by must be an array when present")
        if raw_record.get("approved_by_teams") is not None and not isinstance(
            raw_record.get("approved_by_teams"), list
        ):
            record_errors.append(f"{label}.approved_by_teams must be an array when present")
        for missing_team in approvers.get("missing_approved_by_teams", []):
            record_errors.append(
                f"{label}.approved_by_teams references unknown team {missing_team!r}"
            )
        if not approvers.get("resolved_approved_by"):
            record_errors.append(
                f"{label} must resolve at least one approver via approved_by or approved_by_teams"
            )

        approved_at, approved_at_dt = _parse_timestamp(
            f"{label}.approved_at", raw_record.get("approved_at"), errors=record_errors
        )
        expires_at, expires_at_dt = _parse_timestamp(
            f"{label}.expires_at", raw_record.get("expires_at"), errors=record_errors
        )
        if approved_at_dt and expires_at_dt and expires_at_dt <= approved_at_dt:
            record_errors.append(f"{label}.expires_at must be later than approved_at")

        justification = raw_record.get("justification")
        if not isinstance(justification, str) or not justification.strip():
            record_errors.append(f"{label}.justification must be a non-empty string")
            justification = None
        else:
            justification = justification.strip()

        if record_errors:
            errors.extend(record_errors)
            continue

        normalized.append(
            {
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
        )

    return errors, normalized


def load_exception_policy(root=ROOT):
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


def _matches_skill_target(targets, identity):
    identity = identity if isinstance(identity, dict) else {}
    candidates = [identity.get("qualified_name"), identity.get("name")]
    candidate_set = {item for item in candidates if isinstance(item, str) and item}
    for target in _normalize_string_list(targets):
        if target in candidate_set:
            return True
    return False


def match_active_exceptions(scope, skill_identity, blocking_rule_ids, root=ROOT, policy=None):
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
    usage = []
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
