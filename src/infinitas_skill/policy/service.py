"""Policy validation and promotion commands wired into the unified infinitas CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from infinitas_skill.policy.exception_policy import (
    ExceptionPolicyError,
    load_exception_policy,
)
from infinitas_skill.policy.promotion_report import collect_skill_report
from infinitas_skill.policy.reviews import (
    ReviewPolicyError,
    load_promotion_policy,
)
from infinitas_skill.policy.trace import render_policy_trace
from infinitas_skill.root import ROOT

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


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_policy_pack_selector(
    path: Path, payload: dict[str, Any]
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
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
    clean_names: list[str] = []
    seen: set[str] = set()
    duplicates: list[str] = []
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


def validate_policy_pack(path: Path, expected_name: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    unknown = sorted(set(payload) - NAME_KEYS)
    if unknown:
        errors.append(f"policy pack {expected_name!r} has unsupported keys: {', '.join(unknown)}")
    if "$schema" in payload and not _is_nonempty_string(payload.get("$schema")):
        errors.append(f"policy pack {expected_name!r} $schema must be a string when present")
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, int) or schema_version < 1:
        errors.append(f"policy pack {expected_name!r} schema_version must be an integer >= 1")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
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


def print_promotion_text_report(report: dict[str, Any], *, debug_policy: bool = False) -> None:
    if report["errors"]:
        for message in report["errors"]:
            print(f"FAIL: {message}", file=sys.stderr)
        if debug_policy:
            print(render_policy_trace(report["policy_trace"]), file=sys.stderr)
        return
    print(f"OK: promotion policy passed for {ROOT / report['skill_path']}")
    if debug_policy:
        print(render_policy_trace(report["policy_trace"]))


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


__all__ = [
    "run_check_policy_packs",
    "run_check_promotion",
]
