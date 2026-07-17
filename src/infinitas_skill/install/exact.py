from __future__ import annotations

import argparse
from pathlib import Path

from infinitas_skill.install.common import (
    _apply_plan,
    _check_skill_dir,
    _cleanup_materialized_dirs,
    _emit_payload,
    _load_resolution_plan,
    _materialize_source,
    _remember_cleanup_dir,
    _repo_root,
    _resolve_source,
    _root_step,
)


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


def _install_exact_result_context(
    resolved: dict, name: str, requested_version: str | None, target_dir: str
) -> dict:
    return {
        "qualified_name": resolved.get("qualified_name") or resolved.get("name") or name,
        "source_registry": resolved.get("registry_name") or "self",
        "requested_version": requested_version,
        "resolved_version": resolved.get("version"),
        "target_dir": target_dir,
    }


def _dependencies_require_apply(plan: dict) -> bool:
    return any(
        isinstance(step, dict) and not step.get("root") and step.get("needs_apply")
        for step in plan.get("steps") or []
    )


def _success_payload(context: dict, target_dir: str, applied: int) -> dict:
    return {
        "ok": True,
        **context,
        "manifest_path": str(Path(target_dir) / ".infinitas-skill-install-manifest.json"),
        "state": "up-to-date" if applied == 0 else "installed",
        "applied_steps": applied,
        "next_step": "use-installed-skill",
    }


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
        check_code, check_payload = _check_skill_dir(repo_root=repo_root, skill_dir=source_dir)
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
        context = _install_exact_result_context(
            resolved_payload, name, requested_version, target_dir
        )
        if no_deps and _dependencies_require_apply(plan_payload):
            payload = {
                "ok": False,
                **context,
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
                **context,
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

        return _emit_payload(_success_payload(context, target_dir, applied), as_json=as_json)
    finally:
        _cleanup_materialized_dirs(cleanup_dirs)
