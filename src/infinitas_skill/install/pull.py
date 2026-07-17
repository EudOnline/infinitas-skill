"""Shared immutable pull execution for install workflows."""

from __future__ import annotations

import contextlib
import io
import json
from functools import cmp_to_key
from pathlib import Path
from typing import Any

from infinitas_skill.install.exact import run_install_exact
from infinitas_skill.install.source_resolver_cli import load_candidates
from infinitas_skill.install.version_constraints import compare_versions


def run_pull_skill(
    *,
    repo_root: Path,
    qualified_name: str,
    target_dir: str,
    requested_version: str | None = None,
    source_registry: str | None = None,
    mode: str = "auto",
) -> tuple[int, dict[str, Any]]:
    if mode == "confirm":
        _config, candidates, _blocked = load_candidates(source_registry)
        matching_versions = [
            str(candidate.get("version"))
            for candidate in candidates
            if (
                candidate.get("qualified_name") == qualified_name
                or candidate.get("name") == qualified_name
            )
            and isinstance(candidate.get("version"), str)
            and candidate.get("installable", True)
        ]
        matching_versions.sort(key=cmp_to_key(compare_versions), reverse=True)
        resolved_version = requested_version or (
            matching_versions[0] if matching_versions else None
        )
        return 0, {
            "ok": True,
            "qualified_name": qualified_name,
            "requested_version": requested_version,
            "resolved_version": resolved_version,
            "registry_name": source_registry or "self",
            "target_dir": target_dir,
            "state": "planned",
            "next_step": "confirm-or-run",
        }
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        returncode = run_install_exact(
            root=repo_root,
            name=qualified_name,
            target_dir=target_dir,
            requested_version=requested_version,
            source_registry=source_registry,
            as_json=True,
        )
    raw_output = stdout.getvalue().strip()
    try:
        exact_payload = json.loads(raw_output) if raw_output else {}
    except json.JSONDecodeError:
        exact_payload = {
            "ok": False,
            "state": "failed",
            "error_code": "install-output-invalid",
            "message": raw_output or "install command emitted no payload",
        }
    if returncode != 0:
        return returncode, exact_payload
    lockfile_path = str(Path(target_dir) / ".infinitas-skill-install-manifest.json")
    return 0, {
        "ok": True,
        "qualified_name": exact_payload.get("qualified_name") or qualified_name,
        "requested_version": requested_version,
        "resolved_version": exact_payload.get("resolved_version") or requested_version,
        "registry_name": exact_payload.get("source_registry") or source_registry or "self",
        "target_dir": target_dir,
        "state": "installed",
        "lockfile_path": lockfile_path,
        "installed_files_manifest": lockfile_path,
        "next_step": "sync-or-use",
    }
