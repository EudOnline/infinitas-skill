from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from infinitas_skill.install.distribution_core import DistributionError
from infinitas_skill.install.distribution_materialization import materialize_distribution_source
from infinitas_skill.install.install_manifest import load_install_manifest
from infinitas_skill.install.installed_integrity import (
    InstalledIntegrityError,
    verify_installed_skill,
)
from infinitas_skill.install.installed_integrity_readiness import (
    build_installed_integrity_report_item,
)
from infinitas_skill.install.installed_skill import InstalledSkillError, load_installed_skill
from infinitas_skill.install.integrity_policy import load_install_integrity_policy
from infinitas_skill.install.output import error_to_payload
from infinitas_skill.install.planning import DependencyError
from infinitas_skill.install.service import plan_from_skill_dir
from infinitas_skill.install.skill_validation import (
    SkillValidationError,
    validate_installable_skill_dir,
)
from infinitas_skill.install.source_resolver_cli import (
    SourceResolutionError,
    resolve_source_candidate,
)


def _repo_root(value: str | None) -> Path:
    return Path(value or ".").resolve()


def _emit_payload(payload: dict, *, as_json: bool) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if as_json else None))
    return 0


def _format_warning(value: str | None, *, target_dir: str, skill_name: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    formatted = value.replace("<target-dir>", target_dir)
    formatted = formatted.replace("<skill>", skill_name)
    return formatted


def _run_python_module(
    *,
    repo_root: Path,
    module_name: str,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module_name, *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )


def _resolve_source(
    *,
    repo_root: Path,
    name: str,
    version: str | None = None,
    registry: str | None = None,
    snapshot: str | None = None,
    allow_incubating: bool = False,
) -> tuple[int, dict]:
    try:
        return 0, resolve_source_candidate(
            name,
            root=repo_root,
            version=version,
            registry=registry,
            snapshot=snapshot,
            allow_incubating=allow_incubating,
        )
    except SourceResolutionError as exc:
        return 1, {
            "ok": False,
            "state": "failed",
            "error_code": "resolve-source-failed",
            "message": str(exc),
        }


def _materialize_source(
    *,
    repo_root: Path,
    source_payload: dict,
) -> tuple[int, dict]:
    try:
        return 0, materialize_distribution_source(source_payload, root=repo_root)
    except DistributionError as exc:
        return 1, {
            "ok": False,
            "state": "failed",
            "error_code": "materialize-source-failed",
            "message": str(exc),
        }


def _cleanup_materialized_dirs(cleanup_dirs: list[str]) -> None:
    for value in cleanup_dirs:
        if not isinstance(value, str) or not value.strip():
            continue
        shutil.rmtree(value, ignore_errors=True)


def _remember_cleanup_dir(cleanup_dirs: list[str], payload: dict) -> None:
    cleanup_dir = payload.get("cleanup_dir")
    if isinstance(cleanup_dir, str) and cleanup_dir and cleanup_dir not in cleanup_dirs:
        cleanup_dirs.append(cleanup_dir)


def _check_skill_dir(*, repo_root: Path, skill_dir: str) -> tuple[int, dict | None]:
    try:
        validate_installable_skill_dir(skill_dir, repo_root=repo_root)
    except SkillValidationError as exc:
        return 1, {
            "ok": False,
            "state": "failed",
            "error_code": "invalid-skill-source",
            "message": str(exc),
        }
    else:
        return 0, None


def _load_resolution_plan(
    *,
    repo_root: Path,
    skill_dir: str,
    target_dir: str,
    source_registry: str,
    source_payload: dict,
    mode: str,
) -> tuple[int, dict]:
    try:
        plan = plan_from_skill_dir(
            skill_dir,
            root=repo_root,
            target_dir=target_dir,
            source_registry=source_registry,
            source_info=source_payload,
            mode=mode,
        )
    except DependencyError as exc:
        payload = {"ok": False, "state": "failed", "error_code": "dependency-resolution-failed"}
        payload.update(error_to_payload(exc))
        return 1, payload
    return 0, plan


def _copy_skill_tree(*, source_dir: str, dest_dir: str) -> None:
    destination = Path(dest_dir)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source_dir, destination)


def _update_install_manifest_entry(
    *,
    repo_root: Path,
    target_dir: str,
    source_dir: str,
    dest_dir: str,
    action: str,
    locked_version: str,
    source_payload: dict,
    resolution_plan: dict | None = None,
) -> tuple[int, dict | None]:
    args = [
        str(repo_root),
        target_dir,
        source_dir,
        dest_dir,
        action,
        locked_version,
        json.dumps(source_payload, ensure_ascii=False),
    ]
    if resolution_plan is not None:
        args.append(json.dumps(resolution_plan, ensure_ascii=False))
    result = _run_python_module(
        repo_root=repo_root,
        module_name="infinitas_skill.install.manifest_update_cli",
        args=args,
    )
    if result.returncode == 0:
        return 0, None
    return result.returncode or 1, {
        "ok": False,
        "state": "failed",
        "error_code": "update-install-manifest-failed",
        "message": (result.stderr or result.stdout or "manifest update failed").strip(),
    }


def _load_manifest_entry(target_dir: str, requested_name: str) -> dict:
    manifest = load_install_manifest(target_dir, allow_missing=False)
    skills = manifest.get("skills") or {}
    entry = skills.get(requested_name)
    if not isinstance(entry, dict):
        for candidate in skills.values():
            if not isinstance(candidate, dict):
                continue
            if (
                candidate.get("qualified_name") == requested_name
                or candidate.get("name") == requested_name
            ):
                entry = candidate
                break
    return dict(entry or {})


def _mutation_gate_failure(
    *,
    info: dict,
    report_item: dict,
    target_dir: str,
    state: str = "failed",
) -> dict:
    warning = report_item.get("freshness_warning")
    return {
        "ok": False,
        "qualified_name": info.get("qualified_name"),
        "source_registry": info.get("source_registry"),
        "from_version": info.get("installed_version"),
        "to_version": info.get("installed_version"),
        "target_dir": target_dir,
        "state": state,
        "error_code": report_item.get("mutation_reason_code") or "mutation-blocked",
        "message": warning,
        "next_step": _upgrade_next_step(
            report_item.get("recovery_action"),
            default="refresh-installed-integrity",
        ),
        "freshness_state": report_item.get("freshness_state"),
        "freshness_policy": report_item.get("freshness_policy"),
        "freshness_warning": warning,
        "mutation_readiness": report_item.get("mutation_readiness"),
        "mutation_policy": report_item.get("mutation_policy"),
        "mutation_reason_code": report_item.get("mutation_reason_code"),
        "recovery_action": report_item.get("recovery_action"),
    }


def _apply_plan(
    *,
    repo_root: Path,
    target_dir: str,
    plan: dict,
    root_materialized: dict,
    root_resolved: dict,
    cleanup_dirs: list[str],
    requested_version: str | None = None,
) -> tuple[int, int, dict | None]:
    applied = 0
    root_registry = root_resolved.get("registry_name") or root_resolved.get("source_registry")
    root_snapshot = root_resolved.get("registry_snapshot_id")
    for step in plan.get("steps") or []:
        if not isinstance(step, dict) or not step.get("needs_apply"):
            continue
        step_name = step.get("name") or ""
        step_dest = str(Path(target_dir) / step_name)
        step_action = step.get("action") or "install"
        if step.get("root"):
            step_resolved = root_resolved
            step_materialized = root_materialized
            step_source_dir = step_materialized.get("materialized_path") or ""
            step_locked_version = requested_version or step.get("version") or ""
            step_plan = plan
        else:
            resolve_name = step.get("qualified_name") or step_name
            resolve_code, step_resolved = _resolve_source(
                repo_root=repo_root,
                name=resolve_name,
                version=step.get("version"),
                registry=step.get("registry"),
                snapshot=root_snapshot if step.get("registry") == root_registry else None,
                allow_incubating=step.get("stage") == "incubating",
            )
            if resolve_code != 0:
                return resolve_code, applied, step_resolved
            materialize_code, step_materialized = _materialize_source(
                repo_root=repo_root,
                source_payload=step_resolved,
            )
            if materialize_code != 0:
                return materialize_code, applied, step_materialized
            _remember_cleanup_dir(cleanup_dirs, step_materialized)
            step_source_dir = step_materialized.get("materialized_path") or ""
            step_locked_version = step.get("version") or ""
            step_plan = None

        check_code, check_payload = _check_skill_dir(
            repo_root=repo_root,
            skill_dir=step_source_dir,
        )
        if check_code != 0:
            return check_code, applied, check_payload
        _copy_skill_tree(source_dir=step_source_dir, dest_dir=step_dest)
        update_code, update_payload = _update_install_manifest_entry(
            repo_root=repo_root,
            target_dir=target_dir,
            source_dir=step_source_dir,
            dest_dir=step_dest,
            action=step_action,
            locked_version=step_locked_version,
            source_payload=step_materialized,
            resolution_plan=step_plan,
        )
        if update_code != 0:
            return update_code, applied, update_payload
        applied += 1
    return 0, applied, None


def _root_step(plan: dict) -> dict:
    for step in plan.get("steps") or []:
        if isinstance(step, dict) and step.get("root"):
            return step
    return {}


def _installed_not_found_payload(exc: InstalledSkillError) -> dict:
    return {
        "ok": False,
        "state": "failed",
        "error_code": "installed-skill-not-found",
        "message": str(exc),
    }


def _drift_failure_payload(
    *,
    info: dict,
    report_item: dict,
    target_dir: str,
) -> dict:
    warning = _format_warning(
        (
            "run infinitas install verify <skill> <target-dir> --json or infinitas install repair "
            "<skill> <target-dir> before overwriting local files"
        ),
        target_dir=target_dir,
        skill_name=info["name"],
    )
    payload = {
        "ok": False,
        "qualified_name": info.get("qualified_name"),
        "source_registry": info.get("source_registry"),
        "from_version": info.get("installed_version"),
        "to_version": info.get("installed_version"),
        "target_dir": target_dir,
        "state": "failed",
        "error_code": "drifted-installed-skill",
        "message": warning,
        "next_step": "repair-installed-skill",
        "freshness_state": report_item.get("freshness_state"),
        "freshness_policy": report_item.get("freshness_policy"),
        "freshness_warning": warning,
        "mutation_readiness": "blocked",
        "mutation_policy": report_item.get("mutation_policy"),
        "mutation_reason_code": "drifted-installed-skill",
        "recovery_action": "repair",
    }
    return payload


def _emit_mutation_warning(report_item: dict) -> None:
    warning = report_item.get("freshness_warning")
    if report_item.get("mutation_readiness") == "warning" and warning:
        print(warning, file=sys.stderr)


def _load_installed_info(
    *,
    repo_root: Path,
    target_dir: str,
    requested_name: str,
) -> tuple[dict, dict, dict]:
    try:
        _manifest, item = load_installed_skill(target_dir, requested_name)
    except InstalledSkillError as exc:
        raise InstalledSkillError(str(exc)) from exc

    item = dict(item)
    try:
        verified_integrity = verify_installed_skill(
            target_dir,
            requested_name,
            root=repo_root,
        )
    except InstalledIntegrityError:
        verified_integrity = None
    if isinstance(verified_integrity, dict) and verified_integrity.get("state") != "failed":
        item["integrity"] = verified_integrity

    raw_name = item.get("name")
    installed_name = raw_name if isinstance(raw_name, str) and raw_name else requested_name
    info = {
        "name": installed_name,
        "qualified_name": (
            item.get("source_qualified_name")
            or item.get("qualified_name")
            or item.get("name")
            or requested_name
        ),
        "source_registry": item.get("source_registry") or "self",
        "installed_version": item.get("installed_version") or item.get("version"),
        "integrity": item.get("integrity"),
        "integrity_capability": item.get("integrity_capability"),
        "integrity_reason": item.get("integrity_reason"),
        "last_checked_at": item.get("last_checked_at"),
        "source_distribution_manifest": item.get("source_distribution_manifest"),
        "source_attestation_path": item.get("source_attestation_path"),
    }
    policy = load_install_integrity_policy(repo_root)
    report_item = build_installed_integrity_report_item(
        installed_name,
        {
            "name": info["name"],
            "source_qualified_name": info["qualified_name"],
            "installed_version": info["installed_version"],
            "integrity": info["integrity"],
            "integrity_capability": info["integrity_capability"],
            "integrity_reason": info["integrity_reason"],
            "last_checked_at": info["last_checked_at"],
            "source_distribution_manifest": info["source_distribution_manifest"],
            "source_attestation_path": info["source_attestation_path"],
        },
        policy=policy,
    )
    report_item["freshness_warning"] = _format_warning(
        report_item.get("freshness_warning"),
        target_dir=target_dir,
        skill_name=info["name"] or "",
    )
    return info, report_item, item


def _upgrade_next_step(recovery_action: str | None, *, default: str) -> str:
    return {
        "refresh": "refresh-installed-integrity",
        "repair": "repair-installed-skill",
        "reinstall": "reinstall-installed-skill",
        "backfill-distribution-manifest": "backfill-distribution-manifest",
    }.get(recovery_action or "", default)
