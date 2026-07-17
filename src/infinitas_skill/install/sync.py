from __future__ import annotations

import argparse
from pathlib import Path

from infinitas_skill.install.common import (
    _drift_failure_payload,
    _emit_mutation_warning,
    _emit_payload,
    _installed_not_found_payload,
    _load_installed_info,
    _mutation_gate_failure,
    _repo_root,
    _upgrade_next_step,
)
from infinitas_skill.install.installed_skill import InstalledSkillError
from infinitas_skill.install.pull import run_pull_skill
from infinitas_skill.install.switch import _run_switch_operation


def configure_install_sync_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the installed skill")
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


def build_install_sync_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Sync one installed skill to the latest releasable state from its source",
    )
    return configure_install_sync_parser(parser)


def _readiness_payload(report_item: dict) -> dict:
    return {
        "freshness_state": report_item.get("freshness_state"),
        "freshness_policy": report_item.get("freshness_policy"),
        "freshness_warning": report_item.get("freshness_warning"),
        "mutation_readiness": report_item.get("mutation_readiness"),
        "mutation_policy": report_item.get("mutation_policy"),
        "mutation_reason_code": report_item.get("mutation_reason_code"),
        "recovery_action": report_item.get("recovery_action"),
    }


def _warning_sync_payload(info: dict, report_item: dict, target_dir: str) -> dict:
    return {
        "ok": True,
        "qualified_name": info.get("qualified_name"),
        "source_registry": info.get("source_registry"),
        "installed_version": info.get("installed_version"),
        "target_dir": target_dir,
        "state": "up-to-date",
        "manifest_path": str(Path(target_dir) / ".infinitas-skill-install-manifest.json"),
        "next_step": _upgrade_next_step(
            report_item.get("recovery_action"), default="refresh-installed-integrity"
        ),
        **_readiness_payload(report_item),
    }


def run_install_sync(
    *,
    root: str | Path,
    installed_name: str,
    target_dir: str,
    force: bool = False,
    as_json: bool = False,
) -> int:
    repo_root = _repo_root(str(root))
    try:
        info, report_item, item = _load_installed_info(
            repo_root=repo_root,
            target_dir=target_dir,
            requested_name=installed_name,
        )
    except InstalledSkillError as exc:
        payload = _installed_not_found_payload(exc)
        _emit_payload(payload, as_json=as_json)
        return 1

    if not force and (item.get("integrity") or {}).get("state") == "drifted":
        payload = _drift_failure_payload(
            info=info,
            report_item=report_item,
            target_dir=target_dir,
        )
        _emit_payload(payload, as_json=as_json)
        return 1

    if not force and report_item.get("mutation_readiness") == "blocked":
        payload = _mutation_gate_failure(
            info=info,
            report_item=report_item,
            target_dir=target_dir,
        )
        _emit_payload(payload, as_json=as_json)
        return 1

    if not force:
        _emit_mutation_warning(report_item)
        if report_item.get("mutation_readiness") == "warning":
            payload = _warning_sync_payload(info, report_item, target_dir)
            _emit_payload(payload, as_json=as_json)
            return 0

    resolve_name = info.get("qualified_name") or installed_name
    resolve_registry = info.get("source_registry")
    pull_returncode, pull_payload = run_pull_skill(
        repo_root=repo_root,
        qualified_name=resolve_name,
        target_dir=target_dir,
        source_registry=resolve_registry,
        mode="confirm",
    )
    if pull_returncode != 0:
        _emit_payload(pull_payload, as_json=as_json)
        return pull_returncode

    resolved_version = pull_payload.get("resolved_version") or info.get("installed_version")
    if resolved_version == info.get("installed_version"):
        payload = {
            "ok": True,
            "qualified_name": info.get("qualified_name") or resolve_name,
            "source_registry": resolve_registry,
            "installed_version": info.get("installed_version"),
            "resolved_version": resolved_version,
            "target_dir": target_dir,
            "manifest_path": str(Path(target_dir) / ".infinitas-skill-install-manifest.json"),
            "state": "up-to-date",
            "applied_steps": 0,
            "next_step": "use-installed-skill",
        }
        if not force:
            payload.update(_readiness_payload(report_item))
        return _emit_payload(payload, as_json=as_json)

    switch_returncode, switch_payload = _run_switch_operation(
        root=repo_root,
        installed_name=installed_name,
        target_dir=target_dir,
        requested_version=resolved_version,
        source_registry=resolve_registry,
        qualified_name=resolve_name,
        force=True,
        result_state="synced",
    )
    if not force:
        switch_payload.update(_readiness_payload(report_item))
    switch_payload["resolved_version"] = resolved_version
    switch_payload["installed_version"] = info.get("installed_version")
    switch_payload["applied_steps"] = 1 if switch_returncode == 0 else 0
    _emit_payload(switch_payload, as_json=as_json)
    return switch_returncode
