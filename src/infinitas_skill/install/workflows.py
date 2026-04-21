"""Package-owned CLI helpers for discovery-driven install workflows."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from infinitas_skill.discovery.install_explanation import (
    build_install_explanation,
    build_resolve_explanation,
    build_update_explanation,
    build_upgrade_explanation,
)
from infinitas_skill.discovery.resolver import load_discovery_index, resolve_skill
from infinitas_skill.install.install_manifest import InstallManifestError, load_install_manifest
from infinitas_skill.install.installed_integrity import (
    InstalledIntegrityError,
    build_installed_integrity_report_item,
    verify_installed_skill,
)
from infinitas_skill.install.installed_skill import InstalledSkillError, load_installed_skill
from infinitas_skill.install.integrity_policy import load_install_integrity_policy
from infinitas_skill.install.output import error_to_payload
from infinitas_skill.install.planning import DependencyError
from infinitas_skill.install.service import plan_from_skill_dir


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


def _failure_payload_from_result(
    result: subprocess.CompletedProcess[str], *, error_code: str
) -> dict:
    stdout = (result.stdout or "").strip()
    if stdout:
        try:
            payload = json.loads(stdout)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
    stderr = (result.stderr or "").strip()
    return {
        "ok": False,
        "state": "failed",
        "error_code": error_code,
        "message": stdout or stderr or f"command exited {result.returncode}",
    }


def _run_script(
    *,
    repo_root: Path,
    script_name: str,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(repo_root / "scripts" / script_name), *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
    )


def _run_python_script(
    *,
    repo_root: Path,
    script_name: str,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts" / script_name), *args],
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
    args = [name, "--json"]
    if version:
        args.extend(["--version", version])
    if registry:
        args.extend(["--registry", registry])
    if snapshot:
        args.extend(["--snapshot", snapshot])
    if allow_incubating:
        args.append("--allow-incubating")
    result = _run_python_script(
        repo_root=repo_root,
        script_name="resolve-skill-source.py",
        args=args,
    )
    stdout = (result.stdout or "").strip()
    if result.returncode == 0 and stdout:
        try:
            return 0, json.loads(stdout)
        except json.JSONDecodeError:
            pass
    stderr = (result.stderr or "").strip()
    return result.returncode or 1, {
        "ok": False,
        "state": "failed",
        "error_code": "resolve-source-failed",
        "message": stderr or stdout or "resolve-skill-source.py failed",
    }


def _materialize_source(
    *,
    repo_root: Path,
    source_payload: dict,
) -> tuple[int, dict]:
    result = _run_python_script(
        repo_root=repo_root,
        script_name="materialize-skill-source.py",
        args=["--source-json", json.dumps(source_payload, ensure_ascii=False)],
    )
    stdout = (result.stdout or "").strip()
    if result.returncode == 0 and stdout:
        try:
            return 0, json.loads(stdout)
        except json.JSONDecodeError:
            pass
    stderr = (result.stderr or "").strip()
    return result.returncode or 1, {
        "ok": False,
        "state": "failed",
        "error_code": "materialize-source-failed",
        "message": stderr or stdout or "materialize-skill-source.py failed",
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
    result = _run_script(
        repo_root=repo_root,
        script_name="check-skill.sh",
        args=[skill_dir],
    )
    if result.returncode == 0:
        return 0, None
    return result.returncode or 1, {
        "ok": False,
        "state": "failed",
        "error_code": "invalid-skill-source",
        "message": (result.stderr or result.stdout or "check-skill.sh failed").strip(),
    }


def _load_resolution_plan(
    *,
    skill_dir: str,
    target_dir: str,
    source_registry: str,
    source_payload: dict,
    mode: str,
) -> tuple[int, dict]:
    try:
        plan = plan_from_skill_dir(
            skill_dir,
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
        target_dir,
        source_dir,
        dest_dir,
        action,
        locked_version,
        json.dumps(source_payload, ensure_ascii=False),
    ]
    if resolution_plan is not None:
        args.append(json.dumps(resolution_plan, ensure_ascii=False))
    result = _run_python_script(
        repo_root=repo_root,
        script_name="update-install-manifest.py",
        args=args,
    )
    if result.returncode == 0:
        return 0, None
    return result.returncode or 1, {
        "ok": False,
        "state": "failed",
        "error_code": "update-install-manifest-failed",
        "message": (result.stderr or result.stdout or "update-install-manifest.py failed").strip(),
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
            "run python3 scripts/verify-installed-skill.py <skill> <target-dir> --json "
            "or scripts/repair-installed-skill.sh <skill> <target-dir> before "
            "overwriting local files"
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
        resolve_code, resolved_payload = _resolve_source(
            repo_root=repo_root,
            name=resolve_name,
            version=resolve_version,
            registry=resolve_registry,
            allow_incubating=bool(item.get("source_stage") == "incubating" and to_active),
        )
        if resolve_code != 0:
            return resolve_code, resolved_payload

        materialize_code, materialized_payload = _materialize_source(
            repo_root=repo_root,
            source_payload=resolved_payload,
        )
        if materialize_code != 0:
            return materialize_code, materialized_payload
        _remember_cleanup_dir(cleanup_dirs, materialized_payload)

        source_dir = materialized_payload.get("materialized_path") or ""
        check_code, check_payload = _check_skill_dir(
            repo_root=repo_root,
            skill_dir=source_dir,
        )
        if check_code != 0:
            return check_code, check_payload or {
                "ok": False,
                "state": "failed",
                "error_code": "invalid-skill-source",
                "message": "check-skill.sh failed",
            }

        plan_code, plan_payload = _load_resolution_plan(
            skill_dir=source_dir,
            target_dir=target_dir,
            source_registry=resolve_registry or "self",
            source_payload=materialized_payload,
            mode="install",
        )
        if plan_code != 0:
            return plan_code, plan_payload

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

        target_version = resolved_payload.get("version") or info.get("installed_version")
        payload = {
            "ok": True,
            "qualified_name": resolved_payload.get("qualified_name")
            or info.get("qualified_name")
            or resolve_name,
            "source_registry": resolved_payload.get("registry_name") or resolve_registry,
            "from_version": info.get("installed_version"),
            "to_version": target_version,
            "target_dir": target_dir,
            "state": result_state,
            "manifest_path": str(Path(target_dir) / ".infinitas-skill-install-manifest.json"),
            "next_step": "use-installed-skill",
        }
        if not force:
            payload.update(
                {
                    "freshness_state": report_item.get("freshness_state"),
                    "freshness_policy": report_item.get("freshness_policy"),
                    "freshness_warning": report_item.get("freshness_warning"),
                    "mutation_readiness": report_item.get("mutation_readiness"),
                    "mutation_policy": report_item.get("mutation_policy"),
                    "mutation_reason_code": report_item.get("mutation_reason_code"),
                    "recovery_action": report_item.get("recovery_action"),
                }
            )
        return 0, payload
    finally:
        _cleanup_materialized_dirs(cleanup_dirs)


def _resolve_skill_payload(
    *,
    root: str | Path,
    query: str,
    target_agent: str | None = None,
) -> dict:
    repo_root = _repo_root(str(root))
    try:
        payload = load_discovery_index(repo_root)
        result = resolve_skill(payload=payload, query=query, target_agent=target_agent)
    except Exception as exc:
        result = {
            "ok": False,
            "query": query,
            "state": "failed",
            "resolved": None,
            "candidates": [],
            "requires_confirmation": False,
            "recommended_next_step": "fix discovery-index generation",
            "message": str(exc),
        }

    result["explanation"] = build_resolve_explanation(result)
    return result


def _run_pull_skill(
    *,
    repo_root: Path,
    qualified_name: str,
    target_dir: str,
    requested_version: str | None = None,
    source_registry: str | None = None,
    mode: str = "auto",
) -> tuple[int, dict]:
    command = [str(repo_root / "scripts" / "pull-skill.sh"), qualified_name, target_dir]
    if requested_version:
        command.extend(["--version", requested_version])
    if source_registry:
        command.extend(["--registry", source_registry])
    command.extend(["--mode", mode])
    result = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)

    stdout = (result.stdout or "").strip()
    if stdout:
        try:
            return result.returncode, json.loads(stdout)
        except json.JSONDecodeError:
            pass
    stderr = (result.stderr or "").strip()
    payload = {
        "ok": False,
        "state": "failed",
        "error_code": "pull-command-failed",
        "message": stdout or stderr or f"pull-skill.sh exited {result.returncode}",
    }
    return result.returncode or 1, payload


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

    info = {
        "name": item.get("name") or requested_name,
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
        info["name"],
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
        skill_name=info["name"],
    )
    return info, report_item, item


def _upgrade_next_step(recovery_action: str | None, *, default: str) -> str:
    return {
        "refresh": "refresh-installed-integrity",
        "repair": "repair-installed-skill",
        "reinstall": "reinstall-installed-skill",
        "backfill-distribution-manifest": "backfill-distribution-manifest",
    }.get(recovery_action, default)


def run_install_resolve_skill(
    *,
    root: str | Path,
    query: str,
    target_agent: str | None = None,
    as_json: bool = False,
) -> int:
    payload = _resolve_skill_payload(root=root, query=query, target_agent=target_agent)
    return _emit_payload(payload, as_json=as_json)


def run_install_exact(
    *,
    root: str | Path,
    name: str,
    target_dir: str,
    requested_version: str | None = None,
    source_registry: str | None = None,
    snapshot: str | None = None,
    force: bool = False,
    no_deps: bool = False,
    as_json: bool = False,
) -> int:
    repo_root = _repo_root(str(root))
    cleanup_dirs: list[str] = []
    try:
        resolve_code, resolved_payload = _resolve_source(
            repo_root=repo_root,
            name=name,
            version=requested_version,
            registry=source_registry,
            snapshot=snapshot,
        )
        if resolve_code != 0:
            _emit_payload(resolved_payload, as_json=as_json)
            return resolve_code

        materialize_code, materialized_payload = _materialize_source(
            repo_root=repo_root,
            source_payload=resolved_payload,
        )
        if materialize_code != 0:
            _emit_payload(materialized_payload, as_json=as_json)
            return materialize_code
        _remember_cleanup_dir(cleanup_dirs, materialized_payload)

        source_dir = materialized_payload.get("materialized_path") or ""
        check_code, check_payload = _check_skill_dir(
            repo_root=repo_root,
            skill_dir=source_dir,
        )
        if check_code != 0:
            _emit_payload(check_payload or {}, as_json=as_json)
            return check_code

        plan_code, plan_payload = _load_resolution_plan(
            skill_dir=source_dir,
            target_dir=target_dir,
            source_registry=resolved_payload.get("registry_name") or "self",
            source_payload=materialized_payload,
            mode="install",
        )
        if plan_code != 0:
            _emit_payload(plan_payload, as_json=as_json)
            return plan_code

        root_step = _root_step(plan_payload)
        root_name = root_step.get("name") or resolved_payload.get("name") or name
        root_dest = Path(target_dir) / root_name
        if no_deps:
            for step in plan_payload.get("steps") or []:
                if isinstance(step, dict) and not step.get("root") and step.get("needs_apply"):
                    payload = {
                        "ok": False,
                        "qualified_name": resolved_payload.get("qualified_name")
                        or resolved_payload.get("name")
                        or name,
                        "source_registry": resolved_payload.get("registry_name") or "self",
                        "requested_version": requested_version,
                        "resolved_version": resolved_payload.get("version"),
                        "target_dir": target_dir,
                        "state": "failed",
                        "error_code": "dependencies-require-apply",
                        "message": (
                            "dependency plan requires installing or upgrading dependencies; "
                            "rerun without --no-deps"
                        ),
                        "next_step": "rerun without --no-deps",
                    }
                    _emit_payload(payload, as_json=as_json)
                    return 1
        if root_dest.exists() and root_step.get("action") != "keep" and not force:
            payload = {
                "ok": False,
                "qualified_name": resolved_payload.get("qualified_name")
                or resolved_payload.get("name")
                or name,
                "source_registry": resolved_payload.get("registry_name") or "self",
                "requested_version": requested_version,
                "resolved_version": resolved_payload.get("version"),
                "target_dir": target_dir,
                "state": "failed",
                "error_code": "target-already-exists",
                "message": f"target already exists: {root_dest} (use --force to overwrite)",
                "next_step": "rerun with --force",
            }
            _emit_payload(payload, as_json=as_json)
            return 1

        apply_code, applied, apply_payload = _apply_plan(
            repo_root=repo_root,
            target_dir=target_dir,
            plan=plan_payload,
            root_materialized=materialized_payload,
            root_resolved=resolved_payload,
            cleanup_dirs=cleanup_dirs,
            requested_version=requested_version,
        )
        if apply_code != 0:
            _emit_payload(apply_payload or {}, as_json=as_json)
            return apply_code

        payload = {
            "ok": True,
            "qualified_name": resolved_payload.get("qualified_name")
            or resolved_payload.get("name")
            or name,
            "source_registry": resolved_payload.get("registry_name") or "self",
            "requested_version": requested_version,
            "resolved_version": resolved_payload.get("version"),
            "target_dir": target_dir,
            "manifest_path": str(Path(target_dir) / ".infinitas-skill-install-manifest.json"),
            "state": "up-to-date" if applied == 0 else "installed",
            "applied_steps": applied,
            "next_step": "use-installed-skill",
        }
        return _emit_payload(payload, as_json=as_json)
    finally:
        _cleanup_materialized_dirs(cleanup_dirs)


def run_install_by_name(
    *,
    root: str | Path,
    query: str,
    target_dir: str,
    requested_version: str | None = None,
    target_agent: str | None = None,
    mode: str = "auto",
    as_json: bool = False,
) -> int:
    repo_root = _repo_root(str(root))
    resolve_payload = _resolve_skill_payload(
        root=repo_root,
        query=query,
        target_agent=target_agent,
    )
    state = resolve_payload.get("state") or "failed"
    resolved = resolve_payload.get("resolved") or {}
    candidates = resolve_payload.get("candidates") or []

    if state in {"ambiguous", "not-found", "incompatible", "failed"}:

        def candidate_names() -> str:
            return ", ".join(
                candidate.get("qualified_name") or candidate.get("name") or "?"
                for candidate in candidates
                if isinstance(candidate, dict)
            )

        if state == "ambiguous":
            message = f"ambiguous skill name {query!r}: {candidate_names()}"
            suggested_action = "choose a qualified_name and rerun infinitas install by-name"
            error_code = "ambiguous-skill-name"
        elif state == "not-found":
            message = f"no install candidate found for {query!r}"
            suggested_action = "search discovery-index results or use a known qualified_name"
            error_code = "skill-not-found"
        elif state == "incompatible":
            if target_agent:
                message = (
                    f"no compatible install candidate found for {query!r} "
                    f"with target_agent {target_agent!r}"
                )
                suggested_action = (
                    f"pick a skill compatible with {target_agent} or change --target-agent"
                )
            else:
                message = f"no compatible install candidate found for {query!r}"
                suggested_action = (
                    "pick a compatible skill before retrying infinitas install by-name"
                )
            error_code = "incompatible-target-agent"
        else:
            message = resolve_payload.get("message") or f"skill resolution failed for {query!r}"
            suggested_action = "fix discovery-index generation or resolver errors and retry"
            error_code = "resolver-failed"

        payload = {
            "ok": False,
            "query": query,
            "qualified_name": resolved.get("qualified_name"),
            "source_registry": resolved.get("source_registry"),
            "requested_version": requested_version,
            "resolved_version": resolved.get("resolved_version"),
            "target_dir": target_dir,
            "manifest_path": None,
            "state": "failed",
            "requires_confirmation": False,
            "error_code": error_code,
            "message": message,
            "suggested_action": suggested_action,
            "next_step": resolve_payload.get("recommended_next_step") or suggested_action,
        }
        payload["explanation"] = build_install_explanation(
            resolve_payload,
            payload,
            requested_version=requested_version,
        )
        _emit_payload(payload, as_json=as_json)
        return 1

    requires_confirmation = bool(resolve_payload.get("requires_confirmation"))
    if mode == "auto" and requires_confirmation:
        payload = {
            "ok": False,
            "query": query,
            "qualified_name": resolved.get("qualified_name"),
            "source_registry": resolved.get("source_registry"),
            "requested_version": requested_version,
            "resolved_version": resolved.get("resolved_version"),
            "target_dir": target_dir,
            "manifest_path": None,
            "state": "failed",
            "requires_confirmation": True,
            "error_code": "confirmation-required",
            "next_step": "rerun with --mode confirm and explicit confirmation",
        }
        payload["explanation"] = build_install_explanation(
            resolve_payload,
            payload,
            requested_version=requested_version,
        )
        _emit_payload(payload, as_json=as_json)
        return 1

    qualified_name = resolved.get("qualified_name") or ""
    source_registry = resolved.get("source_registry")
    resolved_version = resolved.get("resolved_version")
    pull_returncode, pull_payload = _run_pull_skill(
        repo_root=repo_root,
        qualified_name=qualified_name,
        target_dir=target_dir,
        requested_version=requested_version or resolved_version,
        source_registry=source_registry,
        mode=mode,
    )

    if pull_returncode != 0:
        _emit_payload(pull_payload, as_json=as_json)
        return pull_returncode

    payload = {
        "ok": pull_payload.get("ok"),
        "query": query,
        "qualified_name": pull_payload.get("qualified_name") or qualified_name,
        "source_registry": pull_payload.get("registry_name") or source_registry,
        "requested_version": requested_version or pull_payload.get("requested_version"),
        "resolved_version": pull_payload.get("resolved_version") or resolved_version,
        "target_dir": target_dir,
        "manifest_path": pull_payload.get("lockfile_path") or pull_payload.get("manifest_path"),
        "state": pull_payload.get("state"),
        "requires_confirmation": requires_confirmation,
        "next_step": (
            "check-update-or-use"
            if pull_payload.get("state") == "installed"
            else pull_payload.get("next_step")
        ),
    }
    payload["explanation"] = build_install_explanation(
        resolve_payload,
        payload,
        requested_version=payload.get("requested_version"),
    )
    return _emit_payload(payload, as_json=as_json)


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

    resolve_name = info.get("qualified_name") or installed_name
    resolve_registry = info.get("source_registry")
    pull_returncode, pull_payload = _run_pull_skill(
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
            payload.update(
                {
                    "freshness_state": report_item.get("freshness_state"),
                    "freshness_policy": report_item.get("freshness_policy"),
                    "freshness_warning": report_item.get("freshness_warning"),
                    "mutation_readiness": report_item.get("mutation_readiness"),
                    "mutation_policy": report_item.get("mutation_policy"),
                    "mutation_reason_code": report_item.get("mutation_reason_code"),
                    "recovery_action": report_item.get("recovery_action"),
                }
            )
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
        switch_payload.update(
            {
                "freshness_state": report_item.get("freshness_state"),
                "freshness_policy": report_item.get("freshness_policy"),
                "freshness_warning": report_item.get("freshness_warning"),
                "mutation_readiness": report_item.get("mutation_readiness"),
                "mutation_policy": report_item.get("mutation_policy"),
                "mutation_reason_code": report_item.get("mutation_reason_code"),
                "recovery_action": report_item.get("recovery_action"),
            }
        )
    switch_payload["resolved_version"] = resolved_version
    switch_payload["installed_version"] = info.get("installed_version")
    switch_payload["applied_steps"] = 1 if switch_returncode == 0 else 0
    _emit_payload(switch_payload, as_json=as_json)
    return switch_returncode


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
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "installed-skill-not-found",
            "message": str(exc),
        }
        _emit_payload(payload, as_json=as_json)
        return 1

    pull_returncode, pull_payload = _run_pull_skill(
        repo_root=repo_root,
        qualified_name=info["qualified_name"],
        target_dir=target_dir,
        source_registry=info["source_registry"],
        mode="confirm",
    )
    if pull_returncode != 0:
        _emit_payload(pull_payload, as_json=as_json)
        return pull_returncode

    latest = pull_payload.get("resolved_version")
    installed = info.get("installed_version")
    next_step = "run upgrade" if latest and latest != installed else "use-installed-skill"
    if report_item.get("mutation_readiness") in {"warning", "blocked"}:
        next_step = _upgrade_next_step(
            report_item.get("recovery_action"),
            default=next_step,
        )

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


def run_install_rollback(
    *,
    root: str | Path,
    installed_name: str,
    target_dir: str,
    steps: int = 1,
    force: bool = False,
    as_json: bool = False,
) -> int:
    repo_root = _repo_root(str(root))
    try:
        current_entry = _load_manifest_entry(target_dir, installed_name)
        actual_name = current_entry.get("name") or installed_name
        manifest = load_install_manifest(target_dir, allow_missing=False)
    except InstallManifestError as exc:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "missing-install-manifest",
            "message": str(exc),
        }
        _emit_payload(payload, as_json=as_json)
        return 1

    history = list((manifest.get("history") or {}).get(actual_name) or [])
    if len(history) < steps:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "rollback-history-missing",
            "message": (
                f"not enough history entries for {actual_name}; have {len(history)}, need {steps}"
            ),
        }
        _emit_payload(payload, as_json=as_json)
        return 1

    target = history[-steps] or {}
    target_version = (
        target.get("locked_version") or target.get("source_version") or target.get("version")
    )
    if not target_version:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "rollback-target-unknown",
            "message": "could not determine rollback target version",
        }
        _emit_payload(payload, as_json=as_json)
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
        payload = {
            "ok": False,
            "qualified_name": info.get("qualified_name"),
            "source_registry": installed_registry,
            "from_version": info.get("installed_version"),
            "target_dir": target_dir,
            "state": "failed",
            "error_code": "cross-source-upgrade-not-allowed",
            "message": (
                f"refusing to switch source registry from {installed_registry!r} "
                f"to {source_registry!r}"
            ),
            "next_step": "rerun without --registry or reinstall explicitly from the new source",
        }
        payload["explanation"] = build_upgrade_explanation(info, payload)
        _emit_payload(payload, as_json=as_json)
        return 1

    pull_returncode, plan_payload = _run_pull_skill(
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
        report_item = {
            **report_item,
            "freshness_state": None,
            "freshness_policy": None,
            "freshness_warning": None,
            "mutation_readiness": "ready",
            "mutation_policy": None,
            "mutation_reason_code": None,
            "recovery_action": "none",
        }

    if not target_version or target_version == info.get("installed_version"):
        payload = {
            "ok": True,
            "qualified_name": info.get("qualified_name"),
            "source_registry": installed_registry,
            "from_version": info.get("installed_version"),
            "to_version": info.get("installed_version"),
            "target_dir": target_dir,
            "state": "up-to-date",
            "manifest_path": None,
            "next_step": "use-installed-skill",
        }
        if mode == "confirm":
            payload.update(
                {
                    "freshness_state": report_item.get("freshness_state"),
                    "freshness_policy": report_item.get("freshness_policy"),
                    "freshness_warning": report_item.get("freshness_warning"),
                    "mutation_readiness": report_item.get("mutation_readiness"),
                    "mutation_policy": report_item.get("mutation_policy"),
                    "mutation_reason_code": report_item.get("mutation_reason_code"),
                    "recovery_action": report_item.get("recovery_action"),
                }
            )
        payload["explanation"] = build_upgrade_explanation(info, payload)
        return _emit_payload(payload, as_json=as_json)

    if mode == "confirm":
        if report_item.get("mutation_readiness") == "blocked":
            payload = {
                "ok": False,
                "qualified_name": info.get("qualified_name"),
                "source_registry": installed_registry,
                "from_version": info.get("installed_version"),
                "to_version": info.get("installed_version"),
                "target_dir": target_dir,
                "state": "failed",
                "error_code": report_item.get("mutation_reason_code")
                or "stale-installed-integrity",
                "message": report_item.get("freshness_warning"),
                "next_step": _upgrade_next_step(
                    report_item.get("recovery_action"),
                    default="refresh-installed-integrity",
                ),
                "freshness_state": report_item.get("freshness_state"),
                "freshness_policy": report_item.get("freshness_policy"),
                "freshness_warning": report_item.get("freshness_warning"),
                "mutation_readiness": "blocked",
                "mutation_policy": report_item.get("mutation_policy"),
                "mutation_reason_code": report_item.get("mutation_reason_code"),
                "recovery_action": report_item.get("recovery_action"),
            }
            payload["explanation"] = build_upgrade_explanation(info, payload)
            _emit_payload(payload, as_json=as_json)
            return 1

        payload = {
            "ok": True,
            "qualified_name": info.get("qualified_name"),
            "source_registry": installed_registry,
            "from_version": info.get("installed_version"),
            "to_version": target_version,
            "target_dir": target_dir,
            "state": "planned",
            "manifest_path": plan_payload.get("manifest_path"),
            "next_step": (
                _upgrade_next_step(
                    report_item.get("recovery_action"),
                    default="run upgrade",
                )
                if report_item.get("mutation_readiness") == "warning"
                else "run upgrade"
            ),
            "freshness_state": report_item.get("freshness_state"),
            "freshness_policy": report_item.get("freshness_policy"),
            "freshness_warning": report_item.get("freshness_warning"),
            "mutation_readiness": report_item.get("mutation_readiness"),
            "mutation_policy": report_item.get("mutation_policy"),
            "mutation_reason_code": report_item.get("mutation_reason_code"),
            "recovery_action": report_item.get("recovery_action"),
        }
        payload["explanation"] = build_upgrade_explanation(info, payload)
        return _emit_payload(payload, as_json=as_json)

    warning = report_item.get("freshness_warning")
    _emit_mutation_warning(report_item)

    if report_item.get("mutation_readiness") == "blocked":
        payload = {
            "ok": False,
            "qualified_name": info.get("qualified_name"),
            "source_registry": installed_registry,
            "from_version": info.get("installed_version"),
            "to_version": info.get("installed_version"),
            "target_dir": target_dir,
            "state": "failed",
            "error_code": report_item.get("mutation_reason_code") or "stale-installed-integrity",
            "message": warning,
            "next_step": _upgrade_next_step(
                report_item.get("recovery_action"),
                default="refresh-installed-integrity",
            ),
            "freshness_state": report_item.get("freshness_state"),
            "freshness_policy": report_item.get("freshness_policy"),
            "freshness_warning": warning,
            "mutation_readiness": "blocked",
            "mutation_policy": report_item.get("mutation_policy"),
            "mutation_reason_code": report_item.get("mutation_reason_code"),
            "recovery_action": report_item.get("recovery_action"),
        }
        payload["explanation"] = build_upgrade_explanation(info, payload)
        _emit_payload(payload, as_json=as_json)
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

    payload = dict(switch_payload)
    payload["explanation"] = build_upgrade_explanation(info, payload)
    return _emit_payload(payload, as_json=as_json)


def configure_install_exact_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("name", help="Skill name or qualified_name to install exactly")
    parser.add_argument("target_dir", help="Target directory for the installed skill")
    parser.add_argument("--version", default=None, help="Optional released version override")
    parser.add_argument("--registry", default=None, help="Optional source registry override")
    parser.add_argument("--snapshot", default=None, help="Optional registry snapshot selector")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the root target if the resolved plan needs to replace it",
    )
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="Fail instead of applying dependency installs or upgrades",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_exact_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Install one exact released skill and apply its dependency plan",
    )
    return configure_install_exact_parser(parser)


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


def configure_install_resolve_skill_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("query", help="Skill name or qualified_name to resolve")
    parser.add_argument("--target-agent", default=None, help="Optional target runtime/agent")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_resolve_skill_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Resolve one install candidate from the discovery index",
    )
    return configure_install_resolve_skill_parser(parser)


def configure_install_by_name_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("query", help="Skill name or qualified_name to install")
    parser.add_argument("target_dir", help="Target directory for the installed skill")
    parser.add_argument("--version", default=None, help="Optional released version override")
    parser.add_argument("--target-agent", default=None, help="Optional target runtime/agent")
    parser.add_argument(
        "--mode",
        choices=("auto", "confirm"),
        default="auto",
        help="Whether to install immediately or only confirm the plan",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


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


def build_install_by_name_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Resolve and install one released skill by discovery-first name lookup",
    )
    return configure_install_by_name_parser(parser)


__all__ = [
    "build_install_exact_parser",
    "build_install_by_name_parser",
    "build_install_check_update_parser",
    "build_install_rollback_parser",
    "build_install_resolve_skill_parser",
    "build_install_switch_parser",
    "build_install_sync_parser",
    "build_install_upgrade_parser",
    "configure_install_exact_parser",
    "configure_install_by_name_parser",
    "configure_install_check_update_parser",
    "configure_install_rollback_parser",
    "configure_install_resolve_skill_parser",
    "configure_install_switch_parser",
    "configure_install_sync_parser",
    "configure_install_upgrade_parser",
    "run_install_exact",
    "run_install_by_name",
    "run_install_check_update",
    "run_install_rollback",
    "run_install_resolve_skill",
    "run_install_switch",
    "run_install_sync",
    "run_install_upgrade",
]
