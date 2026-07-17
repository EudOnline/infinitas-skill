"""Signed release tag creation and publication."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from infinitas_skill.release.policy_state import load_signing_config, signing_key_path
from infinitas_skill.release.release_resolution import resolve_skill
from infinitas_skill.release.service import collect_release_state


class ReleaseTagError(Exception):
    pass


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise ReleaseTagError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def _require_ready(skill_dir: Path, root: Path, mode: str, releaser: str | None) -> dict[str, Any]:
    state = collect_release_state(skill_dir, mode=mode, root=root, releaser=releaser)
    if not state.get("release_ready"):
        errors = state.get("errors") or [f"release state {mode} is not ready"]
        raise ReleaseTagError("; ".join(str(error) for error in errors))
    return state


def _current_remote(root: Path, default_remote: str) -> str:
    upstream = _git(root, "rev-parse", "--abbrev-ref", "@{upstream}", check=False)
    return upstream.split("/", 1)[0] if "/" in upstream else default_remote


def tag_skill_release(
    *,
    root: str | Path,
    skill: str,
    create: bool = False,
    push: bool = False,
    force: bool = False,
    unsigned: bool = False,
    local: bool = False,
    releaser: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    skill_dir = resolve_skill(repo_root, skill)
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    tag = f"skill/{meta['name']}/v{meta['version']}"
    if push:
        create = True
    if local and push:
        raise ReleaseTagError("local tags cannot be pushed")
    if create:
        _require_ready(
            skill_dir,
            repo_root,
            "local-preflight" if local else "preflight",
            releaser,
        )
        if _git(repo_root, "rev-parse", "--verify", tag, check=False):
            if not force:
                raise ReleaseTagError(f"tag already exists: {tag}")
            _git(repo_root, "tag", "-d", tag)
        if unsigned:
            _git(repo_root, "tag", tag)
        else:
            signing = load_signing_config(repo_root)
            key = signing_key_path(repo_root, signing)
            if not key:
                env_name = signing.get("signing_key_env") or "INFINITAS_SKILL_GIT_SIGNING_KEY"
                raise ReleaseTagError(f"set {env_name} or git user.signingkey before tagging")
            command = ["-c", "gpg.format=ssh"]
            env_key = os.environ.get(str(signing.get("signing_key_env") or ""))
            if env_key:
                command.extend(["-c", f"user.signingkey={env_key}"])
            command.extend(["tag", "-s", tag, "-m", tag])
            _git(repo_root, *command)
            _require_ready(skill_dir, repo_root, "local-tag", releaser)
    remote = None
    if push:
        signing = load_signing_config(repo_root)
        remote = _current_remote(repo_root, str(signing.get("default_remote") or "origin"))
        _git(repo_root, "push", remote, f"refs/tags/{tag}")
        if not unsigned:
            _require_ready(skill_dir, repo_root, "stable-release", releaser)
    return {
        "ok": True,
        "skill": meta.get("qualified_name") or meta.get("name"),
        "version": meta.get("version"),
        "tag": tag,
        "created": create,
        "pushed": push,
        "signed": create and not unsigned,
        "remote": remote,
    }


__all__ = ["ReleaseTagError", "tag_skill_release"]
