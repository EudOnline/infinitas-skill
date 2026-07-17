"""Installed-skill inventory, integrity reporting, verification, and repair commands."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

from infinitas_skill.install.common import _emit_payload, _repo_root
from infinitas_skill.install.install_manifest import load_install_manifest, write_install_manifest
from infinitas_skill.install.installed_integrity import (
    InstalledIntegrityError,
    append_integrity_event,
    apply_integrity_history_retention,
    build_install_integrity_snapshot,
    verify_installed_skill,
    write_installed_integrity_snapshot,
)
from infinitas_skill.install.installed_integrity_core import normalize_integrity_events
from infinitas_skill.install.installed_integrity_readiness import (
    build_installed_integrity_report_item,
)
from infinitas_skill.install.installed_skill import InstalledSkillError, load_installed_skill
from infinitas_skill.install.integrity_policy import load_install_integrity_policy


def configure_install_list_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("target_dir", help="Installed skills target directory")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    return parser


def configure_install_report_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    configure_install_list_parser(parser)
    parser.add_argument("--refresh", action="store_true")
    return parser


def configure_install_verify_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("installed_name")
    parser.add_argument("target_dir")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    return parser


def configure_install_repair_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    configure_install_verify_parser(parser)
    return parser


def _refreshed_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _refresh_entry(
    target_dir: Path,
    name: str,
    item: dict,
    *,
    root: Path,
    refreshed_at: str,
) -> dict:
    updated = dict(item)
    installed_dir = target_dir / (updated.get("name") or name)
    snapshot = build_install_integrity_snapshot(
        installed_dir,
        updated,
        root=root,
        verified_at=refreshed_at,
    )
    updated["integrity"] = snapshot["integrity"]
    updated["integrity_capability"] = snapshot["integrity_capability"]
    updated["integrity_reason"] = snapshot["integrity_reason"]
    updated["integrity_events"] = append_integrity_event(
        normalize_integrity_events(updated.get("integrity_events")),
        at=refreshed_at,
        event=(updated.get("integrity") or {}).get("state") or "unknown",
        source="refresh",
        reason=updated.get("integrity_reason"),
    )
    updated["last_checked_at"] = refreshed_at
    updated["updated_at"] = refreshed_at
    return updated


def _refresh_manifest(target_dir: Path, manifest: dict, *, root: Path, policy: dict) -> dict:
    refreshed_at = _refreshed_at()
    updated = dict(manifest)
    updated["skills"] = {
        name: _refresh_entry(
            target_dir,
            name,
            item,
            root=root,
            refreshed_at=refreshed_at,
        )
        for name, item in (manifest.get("skills") or {}).items()
        if isinstance(item, dict)
    }
    updated["updated_at"] = refreshed_at
    updated, archived_by_name = apply_integrity_history_retention(
        updated,
        target_dir=target_dir,
        policy=policy,
    )
    write_install_manifest(target_dir, updated, repo=updated.get("repo"))
    write_installed_integrity_snapshot(
        target_dir,
        updated,
        policy=policy,
        archived_by_name=archived_by_name,
        generated_at=refreshed_at,
    )
    return load_install_manifest(target_dir)


def _report_payload(target_dir: Path, manifest: dict, *, refreshed: bool, policy: dict) -> dict:
    skills = [
        build_installed_integrity_report_item(name, item, policy=policy)
        for name, item in sorted((manifest.get("skills") or {}).items())
        if isinstance(item, dict)
    ]
    return {
        "target_dir": str(target_dir),
        "refreshed": refreshed,
        "skill_count": len(skills),
        "skills": skills,
    }


def _render_inventory(manifest: dict, report: dict) -> None:
    print(f"repo: {manifest.get('repo')}")
    print(f"updated_at: {manifest.get('updated_at')}")
    for item in report.get("skills") or []:
        integrity = item.get("integrity") or {}
        print(
            f"- {item.get('qualified_name')}@{item.get('installed_version')} "
            f"integrity={integrity.get('state')} "
            f"capability={item.get('integrity_capability')} "
            f"freshness={item.get('freshness_state')} "
            f"events={item.get('integrity_event_count', 0)}"
        )


def run_install_report(
    *, root: str | Path, target_dir: str, refresh: bool = False, as_json: bool = False
) -> int:
    repo_root = _repo_root(str(root))
    target = Path(target_dir).resolve()
    manifest = load_install_manifest(target)
    policy = load_install_integrity_policy(repo_root)
    if refresh:
        manifest = _refresh_manifest(target, manifest, root=repo_root, policy=policy)
    payload = _report_payload(target, manifest, refreshed=refresh, policy=policy)
    if as_json:
        return _emit_payload(payload, as_json=True)
    _render_inventory(manifest, payload)
    return 0


def run_install_verify(
    *, root: str | Path, installed_name: str, target_dir: str, as_json: bool = False
) -> int:
    try:
        payload = verify_installed_skill(target_dir, installed_name, root=_repo_root(str(root)))
    except InstalledIntegrityError as exc:
        payload = {"ok": False, "state": "failed", "message": str(exc)}
    _emit_payload(payload, as_json=as_json)
    return 0 if payload.get("state") == "verified" else 1


def run_install_repair(
    *, root: str | Path, installed_name: str, target_dir: str, as_json: bool = False
) -> int:
    try:
        _manifest, item = load_installed_skill(target_dir, installed_name)
    except InstalledSkillError as exc:
        return (
            _emit_payload({"ok": False, "state": "failed", "message": str(exc)}, as_json=as_json)
            or 1
        )

    version = item.get("locked_version") or item.get("installed_version") or item.get("version")
    qualified_name = (
        item.get("source_qualified_name")
        or item.get("qualified_name")
        or item.get("name")
        or installed_name
    )
    registry = item.get("source_registry") or "self"
    if not version:
        _emit_payload(
            {"ok": False, "state": "failed", "message": "repair target version is missing"},
            as_json=as_json,
        )
        return 1

    from infinitas_skill.install.switch import run_install_switch

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = run_install_switch(
            root=root,
            installed_name=installed_name,
            target_dir=target_dir,
            requested_version=version,
            source_registry=registry,
            qualified_name=qualified_name,
            force=True,
            as_json=True,
        )
    try:
        payload = json.loads(output.getvalue())
    except json.JSONDecodeError:
        payload = {"ok": False, "state": "failed", "message": output.getvalue().strip()}
    if code == 0:
        payload["repaired"] = True
    _emit_payload(payload, as_json=as_json)
    return code


__all__ = [
    "configure_install_list_parser",
    "configure_install_report_parser",
    "configure_install_verify_parser",
    "configure_install_repair_parser",
    "run_install_report",
    "run_install_verify",
    "run_install_repair",
]
