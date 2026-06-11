"""Internal helper functions for install workflows.

This module contains utility functions used across the workflow modules.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from infinitas_skill.release.state import ROOT


def repo_root(value: str | None) -> Path:
    return Path(value).resolve() if value else ROOT


def emit_payload(payload: dict, *, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload.get("ok") else 1


def format_warning(value: str | None, *, target_dir: str, skill_name: str) -> str | None:
    if not value:
        return None
    return value.replace("{target_dir}", target_dir).replace("{skill_name}", skill_name)


def failure_payload_from_result(
    result: dict,
    *,
    target_dir: str,
    skill_name: str,
) -> dict:
    """Build a failure payload from a workflow result dict."""
    return {
        "ok": False,
        "error": result.get("error") or "unknown error",
        "target_dir": target_dir,
        "skill_name": skill_name,
        "recovery_action": result.get("recovery_action"),
        "freshness_state": result.get("freshness_state"),
        "freshness_policy": result.get("freshness_policy"),
        "freshness_warning": format_warning(
            result.get("freshness_warning"),
            target_dir=target_dir,
            skill_name=skill_name,
        ),
        "mutation_readiness": result.get("mutation_readiness"),
        "mutation_policy": result.get("mutation_policy"),
        "mutation_reason_code": result.get("mutation_reason_code"),
    }


def run_script(
    script_path: str,
    *args: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run a shell script and return its exit code."""
    cmd = [script_path, *args]
    result = subprocess.run(cmd, cwd=cwd, env=env)
    return result.returncode


def run_python_script(
    script_path: str,
    *args: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run a Python script and return its exit code."""
    cmd = ["python3", script_path, *args]
    result = subprocess.run(cmd, cwd=cwd, env=env)
    return result.returncode


def cleanup_materialized_dirs(cleanup_dirs: list[str]) -> None:
    """Remove temporary materialized directories."""
    for dir_path in cleanup_dirs:
        try:
            shutil.rmtree(dir_path)
        except OSError:
            pass


def remember_cleanup_dir(cleanup_dirs: list[str], payload: dict) -> None:
    """Add a directory to the cleanup list if it exists in the payload."""
    source_dir = payload.get("source_dir")
    if source_dir and source_dir not in cleanup_dirs:
        cleanup_dirs.append(source_dir)


def check_skill_dir(*, repo_root: Path, skill_dir: str) -> tuple[int, dict | None]:
    """Validate that a skill directory exists and is accessible."""
    path = Path(skill_dir)
    if not path.is_absolute():
        path = repo_root / path
    if not path.exists():
        return 1, {"error": f"skill directory not found: {skill_dir}"}
    if not path.is_dir():
        return 1, {"error": f"skill path is not a directory: {skill_dir}"}
    return 0, None


def copy_skill_tree(*, source_dir: str, dest_dir: str) -> None:
    """Copy a skill directory tree to a destination."""
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    shutil.copytree(source_dir, dest_dir)


def emit_mutation_warning(report_item: dict) -> None:
    """Emit a warning about mutation readiness."""
    warning = report_item.get("mutation_warning")
    if warning:
        print(f"WARNING: {warning}", flush=True)


def upgrade_next_step(recovery_action: str | None, *, default: str) -> str:
    """Determine the next step for an upgrade workflow."""
    return recovery_action or default
