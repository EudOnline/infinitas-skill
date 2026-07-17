from __future__ import annotations

import argparse
from pathlib import Path

from infinitas_skill.install.common import (
    _check_skill_dir,
    _cleanup_materialized_dirs,
    _copy_skill_tree,
    _drift_failure_payload,
    _emit_mutation_warning,
    _emit_payload,
    _installed_not_found_payload,
    _load_installed_info,
    _load_resolution_plan,
    _materialize_source,
    _mutation_gate_failure,
    _remember_cleanup_dir,
    _repo_root,
    _resolve_source,
    _update_install_manifest_entry,
)
from infinitas_skill.install.installed_skill import InstalledSkillError


def configure_install_switch_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the installed skill")
    parser.add_argument("--to-version", default=None, help="Switch to an exact released version")
    parser.add_argument(
        "--to-active",
        action="store_true",
        help="Switch to the currently resolved active source instead of an exact version",
    )
    parser.add_argument("--registry", default=None, help="Optional source registry override")
    parser.add_argument("--qualified-name", default=None, help="Optional qualified_name override")
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


def build_install_switch_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Switch one installed skill to another releasable source revision",
    )
    return configure_install_switch_parser(parser)


def _prepare_switch_source(
    *,
    repo_root: Path,
    resolve_name: str,
    resolve_registry: str | None,
    resolve_version: str | None,
    target_dir: str,
    allow_incubating: bool,
    cleanup_dirs: list[str],
) -> tuple[int, dict]:
    resolve_code, resolved = _resolve_source(
        repo_root=repo_root,
        name=resolve_name,
        version=resolve_version,
        registry=resolve_registry,
        allow_incubating=allow_incubating,
    )
    if resolve_code != 0:
        return resolve_code, resolved
    materialize_code, materialized = _materialize_source(
        repo_root=repo_root, source_payload=resolved
    )
    if materialize_code != 0:
        return materialize_code, materialized
    _remember_cleanup_dir(cleanup_dirs, materialized)
    source_dir = materialized.get("materialized_path") or ""
    check_code, check_payload = _check_skill_dir(repo_root=repo_root, skill_dir=source_dir)
    if check_code != 0:
        return check_code, check_payload or {
            "ok": False,
            "state": "failed",
            "error_code": "invalid-skill-source",
            "message": "skill source validation failed",
        }
    plan_code, plan = _load_resolution_plan(
        skill_dir=source_dir,
        target_dir=target_dir,
        source_registry=resolve_registry or "self",
        source_payload=materialized,
        mode="install",
    )
    if plan_code != 0:
        return plan_code, plan
    return 0, {
        "resolved": resolved,
        "materialized": materialized,
        "source_dir": source_dir,
        "plan": plan,
    }


def _switch_success_payload(
    *,
    resolved: dict,
    info: dict,
    resolve_name: str,
    resolve_registry: str | None,
    target_dir: str,
    state: str,
    report_item: dict,
    force: bool,
) -> dict:
    payload = {
        "ok": True,
        "qualified_name": resolved.get("qualified_name")
        or info.get("qualified_name")
        or resolve_name,
        "source_registry": resolved.get("registry_name") or resolve_registry,
        "from_version": info.get("installed_version"),
        "to_version": resolved.get("version") or info.get("installed_version"),
        "target_dir": target_dir,
        "state": state,
        "manifest_path": str(Path(target_dir) / ".infinitas-skill-install-manifest.json"),
        "next_step": "use-installed-skill",
    }
    if not force:
        for field in (
            "freshness_state",
            "freshness_policy",
            "freshness_warning",
            "mutation_readiness",
            "mutation_policy",
            "mutation_reason_code",
            "recovery_action",
        ):
            payload[field] = report_item.get(field)
    return payload


def _run_switch_operation(
    *,
    root: str | Path,
    installed_name: str,
    target_dir: str,
    requested_version: str | None = None,
    to_active: bool = False,
    source_registry: str | None = None,
    qualified_name: str | None = None,
    force: bool = False,
    result_state: str = "switched",
) -> tuple[int, dict]:
    repo_root = _repo_root(str(root))
    cleanup_dirs: list[str] = []
    try:
        try:
            info, report_item, item = _load_installed_info(
                repo_root=repo_root,
                target_dir=target_dir,
                requested_name=installed_name,
            )
        except InstalledSkillError as exc:
            return 1, _installed_not_found_payload(exc)

        if not force and (item.get("integrity") or {}).get("state") == "drifted":
            return 1, _drift_failure_payload(
                info=info,
                report_item=report_item,
                target_dir=target_dir,
            )

        if not force and report_item.get("mutation_readiness") == "blocked":
            return 1, _mutation_gate_failure(
                info=info,
                report_item=report_item,
                target_dir=target_dir,
            )

        if not force:
            _emit_mutation_warning(report_item)

        resolve_name = qualified_name or info.get("qualified_name") or installed_name
        resolve_registry = source_registry or info.get("source_registry")
        resolve_version = None if to_active else requested_version
        prepare_code, prepared = _prepare_switch_source(
            repo_root=repo_root,
            resolve_name=resolve_name,
            resolve_registry=resolve_registry,
            resolve_version=resolve_version,
            target_dir=target_dir,
            allow_incubating=bool(item.get("source_stage") == "incubating" and to_active),
            cleanup_dirs=cleanup_dirs,
        )
        if prepare_code != 0:
            return prepare_code, prepared
        resolved_payload = prepared["resolved"]
        materialized_payload = prepared["materialized"]
        source_dir = prepared["source_dir"]

        dest_name = item.get("name") or resolved_payload.get("name") or installed_name
        dest_dir = str(Path(target_dir) / dest_name)
        _copy_skill_tree(source_dir=source_dir, dest_dir=dest_dir)
        locked_version = (
            resolved_payload.get("version")
            or requested_version
            or item.get("locked_version")
            or item.get("installed_version")
            or ""
        )
        update_code, update_payload = _update_install_manifest_entry(
            repo_root=repo_root,
            target_dir=target_dir,
            source_dir=source_dir,
            dest_dir=dest_dir,
            action="switch",
            locked_version=locked_version,
            source_payload=materialized_payload,
        )
        if update_code != 0:
            return update_code, update_payload or {
                "ok": False,
                "state": "failed",
                "error_code": "update-install-manifest-failed",
                "message": "update-install-manifest.py failed",
            }

        payload = _switch_success_payload(
            resolved=resolved_payload,
            info=info,
            resolve_name=resolve_name,
            resolve_registry=resolve_registry,
            target_dir=target_dir,
            state=result_state,
            report_item=report_item,
            force=force,
        )
        return 0, payload
    finally:
        _cleanup_materialized_dirs(cleanup_dirs)


def run_install_switch(
    *,
    root: str | Path,
    installed_name: str,
    target_dir: str,
    requested_version: str | None = None,
    to_active: bool = False,
    source_registry: str | None = None,
    qualified_name: str | None = None,
    force: bool = False,
    as_json: bool = False,
) -> int:
    if not to_active and not requested_version:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "missing-switch-target",
            "message": "choose either --to-active or --to-version",
        }
        _emit_payload(payload, as_json=as_json)
        return 1
    if to_active and requested_version:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "ambiguous-switch-target",
            "message": "choose either --to-active or --to-version",
        }
        _emit_payload(payload, as_json=as_json)
        return 1

    returncode, payload = _run_switch_operation(
        root=root,
        installed_name=installed_name,
        target_dir=target_dir,
        requested_version=requested_version,
        to_active=to_active,
        source_registry=source_registry,
        qualified_name=qualified_name,
        force=force,
        result_state="switched",
    )
    _emit_payload(payload, as_json=as_json)
    return returncode
