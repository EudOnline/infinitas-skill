from __future__ import annotations

import argparse
from pathlib import Path

from infinitas_skill.discovery.install_explanation import build_update_explanation
from infinitas_skill.install.common import (
    _emit_payload,
    _load_installed_info,
    _repo_root,
    _upgrade_next_step,
)
from infinitas_skill.install.installed_skill import InstalledSkillError
from infinitas_skill.install.pull import run_pull_skill


def configure_install_check_update_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the install manifest")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_check_update_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Check whether an installed skill has a newer same-registry release",
    )
    return configure_install_check_update_parser(parser)


def run_install_check_update(
    *,
    root: str | Path,
    installed_name: str,
    target_dir: str,
    as_json: bool = False,
) -> int:
    repo_root = _repo_root(str(root))
    try:
        info, report_item, _item = _load_installed_info(
            repo_root=repo_root,
            target_dir=target_dir,
            requested_name=installed_name,
        )
    except InstalledSkillError as exc:
        _emit_payload(
            {
                "ok": False,
                "state": "failed",
                "error_code": "installed-skill-not-found",
                "message": str(exc),
            },
            as_json=as_json,
        )
        return 1

    returncode, pull_payload = run_pull_skill(
        repo_root=repo_root,
        qualified_name=info["qualified_name"],
        target_dir=target_dir,
        source_registry=info["source_registry"],
        mode="confirm",
    )
    if returncode != 0:
        _emit_payload(pull_payload, as_json=as_json)
        return returncode

    latest = pull_payload.get("resolved_version")
    installed = info.get("installed_version")
    next_step = "run upgrade" if latest and latest != installed else "use-installed-skill"
    if report_item.get("mutation_readiness") in {"warning", "blocked"}:
        next_step = _upgrade_next_step(report_item.get("recovery_action"), default=next_step)

    payload = {
        "ok": True,
        "qualified_name": info.get("qualified_name"),
        "source_registry": info.get("source_registry"),
        "installed_version": installed,
        "latest_available_version": latest,
        "update_available": bool(latest and latest != installed),
        "state": "update-available" if latest and latest != installed else "up-to-date",
        "next_step": next_step,
        "integrity": info.get("integrity"),
        "freshness_state": report_item.get("freshness_state"),
        "checked_age_seconds": report_item.get("checked_age_seconds"),
        "last_checked_at": report_item.get("last_checked_at"),
        "recommended_action": report_item.get("recommended_action"),
        "freshness_policy": report_item.get("freshness_policy"),
        "freshness_warning": report_item.get("freshness_warning"),
        "mutation_readiness": report_item.get("mutation_readiness"),
        "mutation_policy": report_item.get("mutation_policy"),
        "mutation_reason_code": report_item.get("mutation_reason_code"),
        "recovery_action": report_item.get("recovery_action"),
    }
    payload["explanation"] = build_update_explanation(info, payload)
    return _emit_payload(payload, as_json=as_json)
