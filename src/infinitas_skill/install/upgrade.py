from __future__ import annotations

import argparse
import sys
from pathlib import Path

from infinitas_skill.discovery.install_explanation import build_upgrade_explanation
from infinitas_skill.install.common import (
    _drift_failure_payload,
    _emit_mutation_warning,
    _emit_payload,
    _installed_not_found_payload,
    _load_installed_info,
    _repo_root,
    _upgrade_next_step,
)
from infinitas_skill.install.installed_skill import InstalledSkillError
from infinitas_skill.install.pull import run_pull_skill
from infinitas_skill.install.switch import _run_switch_operation


def configure_install_upgrade_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the installed skill")
    parser.add_argument("--to-version", default=None, help="Optional released version override")
    parser.add_argument(
        "--registry",
        default=None,
        help="Optional source registry override; cross-source upgrade is rejected",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "confirm"),
        default="auto",
        help="Whether to upgrade immediately or only confirm the plan",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass stale/never-verified readiness gates after drift checks",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_upgrade_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Upgrade one installed skill in place from the recorded source registry",
    )
    return configure_install_upgrade_parser(parser)


def _upgrade_readiness(report_item: dict) -> dict:
    return {
        "freshness_state": report_item.get("freshness_state"),
        "freshness_policy": report_item.get("freshness_policy"),
        "freshness_warning": report_item.get("freshness_warning"),
        "mutation_readiness": report_item.get("mutation_readiness"),
        "mutation_policy": report_item.get("mutation_policy"),
        "mutation_reason_code": report_item.get("mutation_reason_code"),
        "recovery_action": report_item.get("recovery_action"),
    }


def _upgrade_context(info: dict, target_dir: str, to_version: str | None) -> dict:
    return {
        "qualified_name": info.get("qualified_name"),
        "source_registry": info.get("source_registry"),
        "from_version": info.get("installed_version"),
        "to_version": to_version,
        "target_dir": target_dir,
    }


def _emit_upgrade_payload(info: dict, payload: dict, *, as_json: bool) -> int:
    payload["explanation"] = build_upgrade_explanation(info, payload)
    return _emit_payload(payload, as_json=as_json)


def _blocked_upgrade_payload(info: dict, report_item: dict, target_dir: str) -> dict:
    return {
        "ok": False,
        **_upgrade_context(info, target_dir, info.get("installed_version")),
        "state": "failed",
        "error_code": report_item.get("mutation_reason_code") or "stale-installed-integrity",
        "message": report_item.get("freshness_warning"),
        "next_step": _upgrade_next_step(
            report_item.get("recovery_action"), default="refresh-installed-integrity"
        ),
        **_upgrade_readiness(report_item),
        "mutation_readiness": "blocked",
    }


def _confirm_upgrade(
    info: dict,
    report_item: dict,
    plan_payload: dict,
    target_dir: str,
    target_version: str,
    *,
    as_json: bool,
) -> int:
    if report_item.get("mutation_readiness") == "blocked":
        payload = _blocked_upgrade_payload(info, report_item, target_dir)
        _emit_upgrade_payload(info, payload, as_json=as_json)
        return 1
    next_step = (
        _upgrade_next_step(report_item.get("recovery_action"), default="run upgrade")
        if report_item.get("mutation_readiness") == "warning"
        else "run upgrade"
    )
    payload = {
        "ok": True,
        **_upgrade_context(info, target_dir, target_version),
        "state": "planned",
        "manifest_path": plan_payload.get("manifest_path"),
        "next_step": next_step,
        **_upgrade_readiness(report_item),
    }
    return _emit_upgrade_payload(info, payload, as_json=as_json)


def _cross_source_payload(info: dict, target_dir: str, requested_registry: str) -> dict:
    installed_registry = info.get("source_registry")
    payload = {
        "ok": False,
        **_upgrade_context(info, target_dir, None),
        "state": "failed",
        "error_code": "cross-source-upgrade-not-allowed",
        "message": (
            f"refusing to switch source registry from {installed_registry!r} "
            f"to {requested_registry!r}"
        ),
        "next_step": "rerun without --registry or reinstall explicitly from the new source",
    }
    payload.pop("to_version")
    return payload


def _force_ready_report(report_item: dict) -> dict:
    return {
        **report_item,
        "freshness_state": None,
        "freshness_policy": None,
        "freshness_warning": None,
        "mutation_readiness": "ready",
        "mutation_policy": None,
        "mutation_reason_code": None,
        "recovery_action": "none",
    }


def run_install_upgrade(
    *,
    root: str | Path,
    installed_name: str,
    target_dir: str,
    requested_version: str | None = None,
    source_registry: str | None = None,
    mode: str = "auto",
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
        payload["explanation"] = build_upgrade_explanation(info, payload)
        if payload.get("message"):
            print(payload["message"], file=sys.stderr)
        _emit_payload(payload, as_json=as_json)
        return 1

    installed_registry = info.get("source_registry")
    if source_registry and source_registry != installed_registry:
        payload = _cross_source_payload(info, target_dir, source_registry)
        _emit_upgrade_payload(info, payload, as_json=as_json)
        return 1

    pull_returncode, plan_payload = run_pull_skill(
        repo_root=repo_root,
        qualified_name=info["qualified_name"],
        target_dir=target_dir,
        requested_version=requested_version,
        source_registry=installed_registry,
        mode="confirm",
    )
    if pull_returncode != 0:
        _emit_payload(plan_payload, as_json=as_json)
        return pull_returncode

    target_version = plan_payload.get("resolved_version") or info.get("installed_version")
    if force:
        report_item = _force_ready_report(report_item)

    if not target_version or target_version == info.get("installed_version"):
        payload = {
            "ok": True,
            **_upgrade_context(info, target_dir, info.get("installed_version")),
            "state": "up-to-date",
            "manifest_path": None,
            "next_step": "use-installed-skill",
        }
        if mode == "confirm":
            payload.update(_upgrade_readiness(report_item))
        return _emit_upgrade_payload(info, payload, as_json=as_json)

    if mode == "confirm":
        return _confirm_upgrade(
            info, report_item, plan_payload, target_dir, target_version, as_json=as_json
        )

    _emit_mutation_warning(report_item)

    if report_item.get("mutation_readiness") == "blocked":
        payload = _blocked_upgrade_payload(info, report_item, target_dir)
        _emit_upgrade_payload(info, payload, as_json=as_json)
        return 1

    switch_returncode, switch_payload = _run_switch_operation(
        root=repo_root,
        installed_name=installed_name,
        target_dir=target_dir,
        requested_version=target_version,
        source_registry=installed_registry,
        qualified_name=info["qualified_name"],
        force=True,
        result_state="installed",
    )
    if switch_returncode != 0:
        switch_payload.setdefault("error_code", "upgrade-command-failed")
        switch_payload.setdefault("state", "failed")
        switch_payload["explanation"] = build_upgrade_explanation(info, switch_payload)
        _emit_payload(switch_payload, as_json=as_json)
        return switch_returncode

    return _emit_upgrade_payload(info, dict(switch_payload), as_json=as_json)
