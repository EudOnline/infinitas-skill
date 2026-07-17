from __future__ import annotations

import argparse
from pathlib import Path

from infinitas_skill.install.common import (
    _emit_payload,
    _load_manifest_entry,
    _repo_root,
)
from infinitas_skill.install.install_manifest import InstallManifestError, load_install_manifest
from infinitas_skill.install.switch import _run_switch_operation


def configure_install_rollback_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the installed skill")
    parser.add_argument(
        "--steps",
        type=int,
        default=1,
        help="How many history entries to walk back",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass stale or never-verified readiness gates after drift checks",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_rollback_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Rollback one installed skill to a recorded prior manifest entry",
    )
    return configure_install_rollback_parser(parser)


def run_install_rollback(
    *,
    root: str | Path,
    installed_name: str,
    target_dir: str,
    steps: int = 1,
    force: bool = False,
    as_json: bool = False,
) -> int:
    if steps < 1:
        _emit_payload(
            {
                "ok": False,
                "state": "failed",
                "error_code": "invalid-rollback-steps",
                "message": f"steps must be a positive integer, got {steps}",
            },
            as_json=as_json,
        )
        return 1
    repo_root = _repo_root(str(root))
    try:
        current_entry = _load_manifest_entry(target_dir, installed_name)
        actual_name = current_entry.get("name") or installed_name
        manifest = load_install_manifest(target_dir, allow_missing=False)
    except InstallManifestError as exc:
        _emit_payload(
            {
                "ok": False,
                "state": "failed",
                "error_code": "missing-install-manifest",
                "message": str(exc),
            },
            as_json=as_json,
        )
        return 1

    history = list((manifest.get("history") or {}).get(actual_name) or [])
    if len(history) < steps:
        _emit_payload(
            {
                "ok": False,
                "state": "failed",
                "error_code": "rollback-history-missing",
                "message": (
                    f"not enough history entries for {actual_name}; "
                    f"have {len(history)}, need {steps}"
                ),
            },
            as_json=as_json,
        )
        return 1

    target = history[-steps] or {}
    target_version = (
        target.get("locked_version") or target.get("source_version") or target.get("version")
    )
    if not target_version:
        _emit_payload(
            {
                "ok": False,
                "state": "failed",
                "error_code": "rollback-target-unknown",
                "message": "could not determine rollback target version",
            },
            as_json=as_json,
        )
        return 1

    returncode, payload = _run_switch_operation(
        root=repo_root,
        installed_name=installed_name,
        target_dir=target_dir,
        requested_version=target_version,
        source_registry=target.get("source_registry") or None,
        qualified_name=target.get("source_qualified_name") or target.get("qualified_name") or None,
        force=force,
        result_state="rolled-back",
    )
    _emit_payload(payload, as_json=as_json)
    return returncode
