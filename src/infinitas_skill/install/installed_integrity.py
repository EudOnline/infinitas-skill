"""Installed-skill integrity verification helpers."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.hashing import sha256_file
from infinitas_skill.install.distribution_core import (
    DistributionError,
    installed_integrity_capability_summary,
    load_json,
)
from infinitas_skill.install.distribution_verification import verify_distribution_manifest
from infinitas_skill.install.installed_integrity_core import (
    default_integrity_capability_fields,
    normalize_integrity_capability_fields,
    normalize_integrity_event,
    normalize_integrity_events,
    normalize_integrity_record,
)
from infinitas_skill.install.installed_integrity_readiness import (
    build_installed_integrity_report_item,
)
from infinitas_skill.install.installed_skill import InstalledSkillError, load_installed_skill
from infinitas_skill.install.integrity_policy import default_install_integrity_policy
from infinitas_skill.release.state import ROOT

logger = logging.getLogger(__name__)

JsonDict = dict[str, Any]


class InstalledIntegrityError(Exception):
    pass


class MissingSignedFileManifestError(InstalledIntegrityError):
    pass


INSTALLED_INTEGRITY_SNAPSHOT_FILENAME = ".infinitas-skill-installed-integrity.json"


def append_integrity_event(
    events: object,
    *,
    at: str,
    event: str,
    source: str,
    reason: str | None = None,
) -> list[dict[str, str]]:
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


def installed_integrity_snapshot_path(target_dir: str | Path) -> Path:
    return (Path(target_dir).resolve() / INSTALLED_INTEGRITY_SNAPSHOT_FILENAME).resolve()


def _load_snapshot_archived_events(
    target_dir: str | Path,
) -> dict[str, list[dict[str, str]]]:
    path = installed_integrity_snapshot_path(target_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("failed to load integrity snapshot: %s", path)
        return {}
    skills = payload.get("skills")
    if not isinstance(skills, list):
        return {}

    archived: dict[str, list[dict[str, str]]] = {}
    for item in skills:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("qualified_name")
        if not isinstance(name, str) or not name:
            continue
        archived[name] = normalize_integrity_events(item.get("archived_integrity_events"))
    return archived


def compact_integrity_history(
    events: object,
    *,
    max_inline_events: int,
    archived_events: object = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    normalized = normalize_integrity_events(events)
    retained_archived = normalize_integrity_events(archived_events)
    if len(normalized) <= max_inline_events:
        return normalized, retained_archived

    overflow = normalized[:-max_inline_events]
    inline = normalized[-max_inline_events:]
    return inline, retained_archived + overflow


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _actual_file_manifest(installed_dir: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for path in sorted(installed_dir.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if not path.resolve().is_relative_to(installed_dir.resolve()):
            continue
        manifest[_relative_path(path, installed_dir)] = sha256_file(path)
    return manifest


def _expected_file_manifest(entries: object) -> dict[str, str]:
    if not isinstance(entries, list) or not entries:
        raise MissingSignedFileManifestError(
            "distribution manifest is missing signed file_manifest entries"
        )

    manifest: dict[str, str] = {}
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


def _resolve_distribution_manifest_path(
    manifest_ref: str, *, distribution_root: Path, root: Path
) -> Path:
    manifest_path = Path(manifest_ref)
    if manifest_path.is_absolute():
        resolved = manifest_path.resolve()
        if not resolved.is_relative_to(root.resolve()):
            raise InstalledIntegrityError(
                f"absolute manifest_ref escapes registry root: {manifest_ref}"
            )
        return resolved
    root_candidate = (distribution_root / manifest_path).resolve()
    if root_candidate.exists():
        return root_candidate
    return (root / manifest_path).resolve()


def installed_integrity_capability_for_source(
    source_info: JsonDict | None, *, root: str | Path | None = None
) -> dict[str, str | None]:
    root = Path(root or ROOT).resolve()
    source_info = source_info or {}
    manifest_ref = source_info.get("distribution_manifest") or source_info.get(
        "source_distribution_manifest"
    )
    if not isinstance(manifest_ref, str) or not manifest_ref:
        return default_integrity_capability_fields()

    raw_distribution_root = source_info.get("distribution_root") or source_info.get(
        "source_distribution_root"
    )
    distribution_root = (
        Path(raw_distribution_root).resolve()
        if isinstance(raw_distribution_root, (str, Path))
        else root
    )
    try:
        manifest_path = _resolve_distribution_manifest_path(
            manifest_ref,
            distribution_root=distribution_root,
            root=root,
        )
        payload = load_json(manifest_path)
    except Exception:
        logger.debug("failed to load distribution manifest for integrity check", exc_info=True)
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
    distribution_root: str | Path | None = None,
    item: JsonDict | None = None,
) -> JsonDict:
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


def build_install_integrity_snapshot(
    installed_dir: str | Path,
    source_info: JsonDict | None,
    *,
    root: str | Path | None = None,
    verified_at: str | None = None,
) -> JsonDict:
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


def build_install_integrity_record(
    installed_dir: str | Path,
    source_info: JsonDict | None,
    *,
    root: str | Path | None = None,
    verified_at: str | None = None,
) -> JsonDict:
    snapshot = build_install_integrity_snapshot(
        installed_dir,
        source_info,
        root=root,
        verified_at=verified_at,
    )
    return snapshot["integrity"]


def apply_integrity_history_retention(
    manifest: JsonDict | None,
    *,
    target_dir: str | Path,
    policy: JsonDict,
) -> tuple[JsonDict, dict[str, list[dict[str, str]]]]:
    manifest = dict(manifest or {})
    skills = manifest.get("skills") or {}
    retained_skills: JsonDict = {}
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
    target_dir: str | Path,
    manifest: JsonDict,
    *,
    policy: JsonDict,
    archived_by_name: dict[str, list[dict[str, str]]] | None = None,
    generated_at: str | None = None,
) -> JsonDict:
    target_dir = Path(target_dir).resolve()
    archived_by_name = archived_by_name or {}
    generated_at = generated_at or datetime.now(timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")

    skills: list[JsonDict] = []
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
    target_dir: str | Path,
    manifest: JsonDict,
    *,
    policy: JsonDict,
    archived_by_name: dict[str, list[dict[str, str]]] | None = None,
    generated_at: str | None = None,
) -> Path:
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


def verify_installed_skill(
    target_dir: str | Path,
    requested_name: str,
    *,
    root: str | Path | None = None,
) -> JsonDict:
    root = Path(root or ROOT).resolve()
    target_dir = Path(target_dir).resolve()

    try:
        _manifest, item = load_installed_skill(target_dir, requested_name)
    except InstalledSkillError as exc:
        raise InstalledIntegrityError(str(exc)) from exc

    installed_name = item.get("name") or requested_name
    if not isinstance(installed_name, str):
        raise InstalledIntegrityError("installed skill is missing name")
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
    "append_integrity_event",
    "installed_integrity_snapshot_path",
    "compact_integrity_history",
    "installed_integrity_capability_for_source",
    "build_install_integrity_snapshot",
    "build_install_integrity_record",
    "apply_integrity_history_retention",
    "build_installed_integrity_snapshot_payload",
    "write_installed_integrity_snapshot",
    "verify_installed_skill",
]
