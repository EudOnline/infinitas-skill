"""Installed-skill integrity verification helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from infinitas_skill.install.distribution import (
    DistributionError,
    installed_integrity_capability_summary,
    load_json,
    sha256_file,
    verify_distribution_manifest,
)
from infinitas_skill.install.installed_skill import InstalledSkillError, load_installed_skill
from infinitas_skill.install.integrity_policy import default_install_integrity_policy
from infinitas_skill.release.state import ROOT


class InstalledIntegrityError(Exception):
    pass


class MissingSignedFileManifestError(InstalledIntegrityError):
    pass


INSTALLED_INTEGRITY_SNAPSHOT_FILENAME = ".infinitas-skill-installed-integrity.json"


def default_integrity_record():
    return {
        "state": "unknown",
        "last_verified_at": None,
        "checked_file_count": 0,
        "release_file_manifest_count": 0,
        "modified_count": 0,
        "missing_count": 0,
        "unexpected_count": 0,
        "modified_files": [],
        "missing_files": [],
        "unexpected_files": [],
    }


def default_integrity_capability_fields():
    return {
        "integrity_capability": "unknown",
        "integrity_reason": None,
    }


def default_integrity_events():
    return []


def default_integrity_freshness():
    return {
        "freshness_state": "never-verified",
        "checked_age_seconds": None,
        "last_checked_at": None,
    }


def normalize_integrity_record(record):
    normalized = default_integrity_record()
    if not isinstance(record, dict):
        return normalized

    state = record.get("state")
    if state in {"unknown", "verified", "drifted"}:
        normalized["state"] = state

    last_verified_at = record.get("last_verified_at")
    if isinstance(last_verified_at, str) and last_verified_at:
        normalized["last_verified_at"] = last_verified_at

    for key in [
        "checked_file_count",
        "release_file_manifest_count",
        "modified_count",
        "missing_count",
        "unexpected_count",
    ]:
        value = record.get(key)
        if isinstance(value, int) and value >= 0:
            normalized[key] = value

    for key in ["modified_files", "missing_files", "unexpected_files"]:
        value = record.get(key)
        if isinstance(value, list):
            normalized[key] = [item for item in value if isinstance(item, str) and item]

    return normalized


def normalize_integrity_capability_fields(capability=None, reason=None):
    normalized = default_integrity_capability_fields()
    if capability == "supported":
        normalized["integrity_capability"] = "supported"
        normalized["integrity_reason"] = None
        return normalized
    if isinstance(reason, str) and reason:
        normalized["integrity_reason"] = reason
    return normalized


def normalize_integrity_event(event):
    if not isinstance(event, dict):
        return None
    normalized = {}
    for key in ["at", "event", "source"]:
        value = event.get(key)
        if not isinstance(value, str) or not value:
            return None
        normalized[key] = value
    reason = event.get("reason")
    if isinstance(reason, str) and reason:
        normalized["reason"] = reason
    return normalized


def normalize_integrity_events(events):
    if not isinstance(events, list):
        return default_integrity_events()
    normalized = []
    for item in events:
        event = normalize_integrity_event(item)
        if event is not None:
            normalized.append(event)
    return normalized


def append_integrity_event(events, *, at, event, source, reason=None):
    normalized = normalize_integrity_events(events)
    payload = {
        "at": at,
        "event": event,
        "source": source,
    }
    if isinstance(reason, str) and reason:
        payload["reason"] = reason
    normalized_event = normalize_integrity_event(payload)
    if normalized_event is None:
        raise InstalledIntegrityError("integrity event payload is invalid")
    normalized.append(normalized_event)
    return normalized


def _normalize_timestamp_string(value):
    return value if isinstance(value, str) and value else None


def _parse_timestamp(value):
    value = _normalize_timestamp_string(value)
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def installed_integrity_snapshot_path(target_dir):
    return (Path(target_dir).resolve() / INSTALLED_INTEGRITY_SNAPSHOT_FILENAME).resolve()


def _load_snapshot_archived_events(target_dir):
    path = installed_integrity_snapshot_path(target_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    skills = payload.get("skills")
    if not isinstance(skills, list):
        return {}

    archived = {}
    for item in skills:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("qualified_name")
        if not isinstance(name, str) or not name:
            continue
        archived[name] = normalize_integrity_events(item.get("archived_integrity_events"))
    return archived


def compact_integrity_history(events, *, max_inline_events, archived_events=None):
    normalized = normalize_integrity_events(events)
    retained_archived = normalize_integrity_events(archived_events)
    if len(normalized) <= max_inline_events:
        return normalized, retained_archived

    overflow = normalized[:-max_inline_events]
    inline = normalized[-max_inline_events:]
    return inline, retained_archived + overflow


def _relative_path(path: Path, root: Path):
    return path.relative_to(root).as_posix()


def _actual_file_manifest(installed_dir: Path):
    manifest = {}
    for path in sorted(installed_dir.rglob("*")):
        if not path.is_file():
            continue
        manifest[_relative_path(path, installed_dir)] = sha256_file(path)
    return manifest


def _expected_file_manifest(entries):
    if not isinstance(entries, list) or not entries:
        raise MissingSignedFileManifestError(
            "distribution manifest is missing signed file_manifest entries"
        )

    manifest = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise InstalledIntegrityError(
                "distribution manifest file_manifest entries must be objects"
            )
        rel_path = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(rel_path, str) or not rel_path:
            raise InstalledIntegrityError(
                "distribution manifest file_manifest entry is missing path"
            )
        if not isinstance(digest, str) or not digest:
            raise InstalledIntegrityError(
                f"distribution manifest file_manifest entry {rel_path!r} is missing sha256"
            )
        manifest[rel_path] = digest
    return manifest


def _resolve_distribution_manifest_path(manifest_ref: str, *, distribution_root: Path, root: Path):
    manifest_path = Path(manifest_ref)
    if manifest_path.is_absolute():
        return manifest_path.resolve()
    root_candidate = (distribution_root / manifest_path).resolve()
    if root_candidate.exists():
        return root_candidate
    return (root / manifest_path).resolve()


def installed_integrity_capability_for_source(source_info, *, root=None):
    root = Path(root or ROOT).resolve()
    source_info = source_info or {}
    manifest_ref = source_info.get("distribution_manifest") or source_info.get(
        "source_distribution_manifest"
    )
    if not isinstance(manifest_ref, str) or not manifest_ref:
        return default_integrity_capability_fields()

    distribution_root = Path(
        source_info.get("distribution_root") or source_info.get("source_distribution_root") or root
    ).resolve()
    try:
        manifest_path = _resolve_distribution_manifest_path(
            manifest_ref,
            distribution_root=distribution_root,
            root=root,
        )
        payload = load_json(manifest_path)
    except Exception:
        return default_integrity_capability_fields()

    summary = installed_integrity_capability_summary(payload)
    return normalize_integrity_capability_fields(
        summary.get("installed_integrity_capability"),
        summary.get("installed_integrity_reason"),
    )


def _verify_installed_dir(
    installed_dir: Path,
    manifest_ref: str,
    *,
    root: Path,
    distribution_root: Path | None = None,
    item=None,
):
    distribution_root = Path(distribution_root or root).resolve()
    try:
        verified_distribution = verify_distribution_manifest(
            manifest_ref, root=distribution_root, attestation_root=root
        )
    except DistributionError as exc:
        raise InstalledIntegrityError(str(exc)) from exc

    expected_files = _expected_file_manifest(
        (verified_distribution.get("manifest") or {}).get("file_manifest")
    )
    actual_files = _actual_file_manifest(installed_dir)

    modified_files = sorted(
        path
        for path, digest in expected_files.items()
        if path in actual_files and actual_files[path] != digest
    )
    missing_files = sorted(path for path in expected_files if path not in actual_files)
    unexpected_files = sorted(path for path in actual_files if path not in expected_files)
    state = (
        "verified"
        if not modified_files and not missing_files and not unexpected_files
        else "drifted"
    )

    payload = {
        "state": state,
        "release_file_manifest_count": len(expected_files),
        "checked_file_count": len(expected_files),
        "actual_file_count": len(actual_files),
        "modified_files": modified_files,
        "missing_files": missing_files,
        "unexpected_files": unexpected_files,
        "modified_count": len(modified_files),
        "missing_count": len(missing_files),
        "unexpected_count": len(unexpected_files),
    }
    if item is not None:
        recorded_integrity = normalize_integrity_record(item.get("integrity"))
        payload.update(
            {
                "qualified_name": item.get("source_qualified_name")
                or item.get("qualified_name")
                or item.get("name"),
                "installed_name": item.get("name"),
                "installed_version": item.get("installed_version") or item.get("version"),
                "installed_path": str(installed_dir),
                "source_registry": item.get("source_registry") or "self",
                "source_distribution_manifest": manifest_ref,
                "source_attestation_path": item.get("source_attestation_path"),
                "last_verified_at": recorded_integrity.get("last_verified_at"),
            }
        )
    return payload


def build_install_integrity_snapshot(installed_dir, source_info, *, root=None, verified_at=None):
    root = Path(root or ROOT).resolve()
    installed_dir = Path(installed_dir).resolve()
    source_info = source_info or {}
    capability = installed_integrity_capability_for_source(source_info, root=root)

    manifest_ref = source_info.get("distribution_manifest") or source_info.get(
        "source_distribution_manifest"
    )
    distribution_root = source_info.get("distribution_root") or source_info.get(
        "source_distribution_root"
    )
    attestation_ref = source_info.get("distribution_attestation") or source_info.get(
        "source_attestation_path"
    )
    if (
        not isinstance(manifest_ref, str)
        or not manifest_ref
        or not isinstance(attestation_ref, str)
        or not attestation_ref
    ):
        return {
            "integrity": normalize_integrity_record({"state": "unknown"}),
            **capability,
        }

    try:
        payload = _verify_installed_dir(
            installed_dir, manifest_ref, root=root, distribution_root=distribution_root
        )
    except MissingSignedFileManifestError:
        return {
            "integrity": normalize_integrity_record({"state": "unknown"}),
            **capability,
        }

    payload["last_verified_at"] = verified_at
    return {
        "integrity": normalize_integrity_record(payload),
        **capability,
    }


def build_install_integrity_record(installed_dir, source_info, *, root=None, verified_at=None):
    snapshot = build_install_integrity_snapshot(
        installed_dir,
        source_info,
        root=root,
        verified_at=verified_at,
    )
    return snapshot["integrity"]


def build_integrity_freshness(item, *, policy=None, now=None):
    item = item or {}
    policy = policy or default_install_integrity_policy()
    normalized = default_integrity_freshness()
    integrity = normalize_integrity_record(item.get("integrity"))
    last_checked_at = _normalize_timestamp_string(item.get("last_checked_at"))
    checked_at = last_checked_at or integrity.get("last_verified_at")
    checked_at_dt = _parse_timestamp(checked_at)
    if checked_at_dt is None:
        return normalized

    if now is None:
        now_dt = datetime.now(timezone.utc)
    elif isinstance(now, datetime):
        now_dt = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)
    else:
        now_dt = _parse_timestamp(now)
        if now_dt is None:
            now_dt = datetime.now(timezone.utc)

    stale_after_hours = (
        (policy.get("freshness") or {}).get("stale_after_hours")
    ) or default_install_integrity_policy()["freshness"]["stale_after_hours"]
    age_seconds = max(0, int((now_dt - checked_at_dt).total_seconds()))
    normalized["freshness_state"] = "stale" if age_seconds > (stale_after_hours * 3600) else "fresh"
    normalized["checked_age_seconds"] = age_seconds
    normalized["last_checked_at"] = last_checked_at
    return normalized


def _policy_choice(policy, key):
    freshness_policy = (policy.get("freshness") or {}) if isinstance(policy, dict) else {}
    default_freshness = default_install_integrity_policy()["freshness"]
    return freshness_policy.get(key) or default_freshness[key]


def _warning_for_recovery_action(recovery_action):
    if recovery_action == "refresh":
        return (
            "run python3 scripts/report-installed-integrity.py "
            "<target-dir> --refresh before overwriting local files"
        )
    if recovery_action == "repair":
        return (
            "run python3 scripts/verify-installed-skill.py <skill> <target-dir> --json "
            "or scripts/repair-installed-skill.sh <skill> <target-dir> before "
            "overwriting local files"
        )
    if recovery_action == "backfill-distribution-manifest":
        return (
            "backfill the signed distribution manifest or reinstall the skill "
            "from a trusted immutable source before overwriting local files"
        )
    if recovery_action == "reinstall":
        return "reinstall the skill from a trusted immutable source before overwriting local files"
    return None


def recovery_action_for_integrity(
    integrity_record, *, capability="unknown", reason=None, freshness_state="never-verified"
):
    integrity = normalize_integrity_record(integrity_record)
    state = integrity.get("state")
    if state == "drifted":
        return "repair"
    if freshness_state == "stale":
        return "refresh"
    if freshness_state == "never-verified":
        if capability == "supported":
            return "refresh"
        if capability == "unknown" and reason == "missing-signed-file-manifest":
            return "backfill-distribution-manifest"
        return "reinstall"
    if capability == "unknown" and reason == "missing-signed-file-manifest":
        return "backfill-distribution-manifest"
    if state == "verified":
        return "none"
    return "reinstall"


def evaluate_installed_mutation_readiness(item, *, policy=None, now=None):
    item = item or {}
    policy = policy or default_install_integrity_policy()
    integrity = normalize_integrity_record(item.get("integrity"))
    capability_fields = normalize_integrity_capability_fields(
        item.get("integrity_capability"),
        item.get("integrity_reason"),
    )
    freshness = build_integrity_freshness(item, policy=policy, now=now)
    freshness_state = freshness.get("freshness_state")
    recovery_action = recovery_action_for_integrity(
        integrity,
        capability=capability_fields.get("integrity_capability"),
        reason=capability_fields.get("integrity_reason"),
        freshness_state=freshness_state,
    )

    mutation_readiness = "ready"
    mutation_policy = None
    mutation_reason_code = None
    if integrity.get("state") == "drifted":
        mutation_readiness = "blocked"
        mutation_reason_code = "drifted-installed-skill"
        recovery_action = "repair"
    elif freshness_state == "stale":
        mutation_policy = _policy_choice(policy, "stale_policy")
        mutation_readiness = {
            "ignore": "ready",
            "warn": "warning",
            "fail": "blocked",
        }[mutation_policy]
        if mutation_readiness != "ready":
            mutation_reason_code = "stale-installed-integrity"
    elif freshness_state == "never-verified":
        mutation_policy = _policy_choice(policy, "never_verified_policy")
        mutation_readiness = {
            "ignore": "ready",
            "warn": "warning",
            "fail": "blocked",
        }[mutation_policy]
        if mutation_readiness != "ready":
            mutation_reason_code = "never-verified-installed-integrity"

    warning = None
    if mutation_readiness != "ready":
        warning = _warning_for_recovery_action(recovery_action)

    return {
        "freshness_state": freshness_state,
        "checked_age_seconds": freshness.get("checked_age_seconds"),
        "last_checked_at": freshness.get("last_checked_at"),
        "freshness_policy": mutation_policy
        if freshness_state in {"stale", "never-verified"}
        else None,
        "stale": freshness_state == "stale",
        "blocking": mutation_readiness == "blocked",
        "warning": warning,
        "mutation_readiness": mutation_readiness,
        "mutation_policy": mutation_policy,
        "mutation_reason_code": mutation_reason_code,
        "recovery_action": recovery_action,
    }


def evaluate_installed_freshness_gate(item, *, policy=None, now=None):
    readiness = evaluate_installed_mutation_readiness(item, policy=policy, now=now)
    return {
        "freshness_state": readiness.get("freshness_state"),
        "checked_age_seconds": readiness.get("checked_age_seconds"),
        "last_checked_at": readiness.get("last_checked_at"),
        "freshness_policy": readiness.get("freshness_policy"),
        "stale": readiness.get("stale"),
        "blocking": readiness.get("blocking"),
        "reason_code": readiness.get("mutation_reason_code"),
        "warning": readiness.get("warning"),
    }


def recommended_action_for_integrity(
    integrity_record, *, capability="unknown", reason=None, freshness_state="never-verified"
):
    return recovery_action_for_integrity(
        integrity_record,
        capability=capability,
        reason=reason,
        freshness_state=freshness_state,
    )


def build_installed_integrity_report_item(name, item, *, policy=None, now=None):
    item = item or {}
    integrity = normalize_integrity_record(item.get("integrity"))
    capability_fields = normalize_integrity_capability_fields(
        item.get("integrity_capability"),
        item.get("integrity_reason"),
    )
    events = normalize_integrity_events(item.get("integrity_events"))
    readiness = evaluate_installed_mutation_readiness(item, policy=policy, now=now)
    return {
        "name": item.get("name") or name,
        "qualified_name": item.get("source_qualified_name")
        or item.get("qualified_name")
        or item.get("name")
        or name,
        "installed_version": item.get("installed_version") or item.get("version"),
        "integrity": integrity,
        "integrity_capability": capability_fields.get("integrity_capability"),
        "integrity_reason": capability_fields.get("integrity_reason"),
        "last_verified_at": integrity.get("last_verified_at"),
        "freshness_state": readiness.get("freshness_state"),
        "checked_age_seconds": readiness.get("checked_age_seconds"),
        "last_checked_at": readiness.get("last_checked_at"),
        "freshness_policy": readiness.get("freshness_policy"),
        "freshness_warning": readiness.get("warning"),
        "mutation_readiness": readiness.get("mutation_readiness"),
        "mutation_policy": readiness.get("mutation_policy"),
        "mutation_reason_code": readiness.get("mutation_reason_code"),
        "recovery_action": readiness.get("recovery_action"),
        "recommended_action": recommended_action_for_integrity(
            integrity,
            capability=capability_fields.get("integrity_capability"),
            reason=capability_fields.get("integrity_reason"),
            freshness_state=readiness.get("freshness_state"),
        ),
        "integrity_events": events,
    }


def apply_integrity_history_retention(manifest, *, target_dir, policy):
    manifest = dict(manifest or {})
    skills = manifest.get("skills") or {}
    retained_skills = {}
    archived_by_name = _load_snapshot_archived_events(target_dir)
    max_inline_events = (
        (policy.get("history") or {}).get("max_inline_events")
    ) or default_install_integrity_policy()["history"]["max_inline_events"]

    for name, item in skills.items():
        if not isinstance(item, dict):
            retained_skills[name] = item
            continue
        current = dict(item)
        inline_events, archived_events = compact_integrity_history(
            current.get("integrity_events"),
            max_inline_events=max_inline_events,
            archived_events=archived_by_name.get(name),
        )
        current["integrity_events"] = inline_events
        retained_skills[name] = current
        archived_by_name[name] = archived_events

    manifest["skills"] = retained_skills
    return manifest, archived_by_name


def build_installed_integrity_snapshot_payload(
    target_dir, manifest, *, policy, archived_by_name=None, generated_at=None
):
    target_dir = Path(target_dir).resolve()
    archived_by_name = archived_by_name or {}
    generated_at = generated_at or datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")

    skills = []
    for name, item in sorted((manifest.get("skills") or {}).items()):
        if not isinstance(item, dict):
            continue
        report_item = build_installed_integrity_report_item(
            name, item, policy=policy, now=generated_at
        )
        report_item["archived_integrity_events"] = normalize_integrity_events(
            archived_by_name.get(name)
        )
        skills.append(report_item)

    return {
        "$schema": "https://infinitas-skill.local/schemas/installed-integrity-snapshot.schema.json",
        "schema_version": 1,
        "generated_at": generated_at,
        "target_dir": str(target_dir),
        "policy": policy,
        "skill_count": len(skills),
        "skills": skills,
    }


def write_installed_integrity_snapshot(
    target_dir, manifest, *, policy, archived_by_name=None, generated_at=None
):
    payload = build_installed_integrity_snapshot_payload(
        target_dir,
        manifest,
        policy=policy,
        archived_by_name=archived_by_name,
        generated_at=generated_at,
    )
    path = installed_integrity_snapshot_path(target_dir)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def verify_installed_skill(target_dir, requested_name, *, root=None):
    root = Path(root or ROOT).resolve()
    target_dir = Path(target_dir).resolve()

    try:
        _manifest, item = load_installed_skill(target_dir, requested_name)
    except InstalledSkillError as exc:
        raise InstalledIntegrityError(str(exc)) from exc

    installed_name = item.get("name") or requested_name
    installed_dir = target_dir / installed_name
    if not installed_dir.is_dir():
        raise InstalledIntegrityError(f"installed skill directory is missing: {installed_dir}")

    manifest_ref = item.get("source_distribution_manifest")
    distribution_root = item.get("source_distribution_root")
    attestation_ref = item.get("source_attestation_path")
    if not isinstance(manifest_ref, str) or not manifest_ref:
        raise InstalledIntegrityError("installed skill is missing source_distribution_manifest")
    if not isinstance(attestation_ref, str) or not attestation_ref:
        raise InstalledIntegrityError("installed skill is missing source_attestation_path")
    payload = _verify_installed_dir(
        installed_dir,
        manifest_ref,
        root=root,
        distribution_root=distribution_root,
        item=item,
    )
    payload["installed_name"] = installed_name
    return payload


__all__ = [
    "InstalledIntegrityError",
    "MissingSignedFileManifestError",
    "INSTALLED_INTEGRITY_SNAPSHOT_FILENAME",
    "default_integrity_record",
    "default_integrity_capability_fields",
    "default_integrity_events",
    "default_integrity_freshness",
    "normalize_integrity_record",
    "normalize_integrity_capability_fields",
    "normalize_integrity_event",
    "normalize_integrity_events",
    "append_integrity_event",
    "installed_integrity_snapshot_path",
    "compact_integrity_history",
    "installed_integrity_capability_for_source",
    "build_install_integrity_snapshot",
    "build_install_integrity_record",
    "build_integrity_freshness",
    "recovery_action_for_integrity",
    "evaluate_installed_mutation_readiness",
    "evaluate_installed_freshness_gate",
    "recommended_action_for_integrity",
    "build_installed_integrity_report_item",
    "apply_integrity_history_retention",
    "build_installed_integrity_snapshot_payload",
    "write_installed_integrity_snapshot",
    "verify_installed_skill",
]
