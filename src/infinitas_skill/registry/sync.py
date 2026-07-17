"""Registry source synchronization and one-way mirroring."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from infinitas_skill.install.registry_source_primitives import (
    canonical_pin_ref,
    extract_git_host,
    normalized_allowed_hosts,
    normalized_allowed_refs,
    normalized_pin,
    normalized_update_policy,
    resolve_registry_root,
    short_pin_value,
)
from infinitas_skill.install.registry_sources import (
    find_registry,
    load_registry_config,
    validate_registry_config,
)
from infinitas_skill.registry.refresh_state import write_refresh_state
from infinitas_skill.registry.snapshot import resolve_snapshot_selector


class RegistrySyncError(Exception):
    pass


def _git(*args: str, cwd: Path | None = None) -> str:
    command = ["git"]
    if cwd is not None:
        command.extend(["-C", str(cwd)])
    command.extend(args)
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise RegistrySyncError(message or f"git command failed: {' '.join(command)}")
    return result.stdout.strip()


def _load_registry(root: Path, name: str) -> dict[str, Any]:
    config = load_registry_config(root)
    errors = validate_registry_config(root, config)
    if errors:
        raise RegistrySyncError("invalid registry-sources.json: " + "; ".join(errors))
    registry = find_registry(config, name)
    if registry is None:
        raise RegistrySyncError(f"unknown registry: {name}")
    if not registry.get("enabled", True):
        raise RegistrySyncError(f"registry is disabled: {name}")
    return registry


def _snapshot_path(root: Path, name: str, selector: str) -> Path:
    record = resolve_snapshot_selector(root, name, selector)
    if record is None:
        raise RegistrySyncError(f"snapshot {selector!r} not found for registry {name!r}")
    summary = record.get("summary") or {}
    raw_path = summary.get("snapshot_root")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise RegistrySyncError(f"snapshot {selector!r} is missing snapshot_root metadata")
    path = Path(raw_path)
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.exists():
        raise RegistrySyncError(f"snapshot {selector!r} is missing its registry tree")
    return resolved


def _validate_origin(
    path: Path,
    *,
    name: str,
    configured_host: str | None,
    allowed_hosts: list[str],
) -> None:
    origin_url = _git("config", "--get", "remote.origin.url", cwd=path)
    origin_host = extract_git_host(origin_url)
    if configured_host and origin_host and origin_host != configured_host:
        raise RegistrySyncError(
            f"registry {name} origin host {origin_host!r} does not match {configured_host!r}"
        )
    if origin_host and origin_host not in allowed_hosts:
        raise RegistrySyncError(f"registry {name} origin host {origin_host!r} is not allowed")


def _prepare_git_cache(
    root: Path,
    registry: dict[str, Any],
    path: Path,
    *,
    force: bool,
) -> None:
    cache_root = (root / ".cache" / "registries").resolve()
    if force and path.exists() and path.resolve().is_relative_to(cache_root):
        shutil.rmtree(path, ignore_errors=True)
    url = registry.get("url")
    if not isinstance(url, str) or not url:
        raise RegistrySyncError(f"git registry {registry.get('name')} missing url")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not (path / ".git").exists() and any(path.iterdir()):
        raise RegistrySyncError(f"target cache path exists and is not a git repo: {path}")
    if not (path / ".git").exists():
        _git("clone", "--no-checkout", url, str(path))


def _resolve_target_commit(
    path: Path,
    *,
    name: str,
    pin: dict,
    update_policy: dict,
    desired_ref: str | None,
    allowed_refs: list[str],
) -> str:
    mode = update_policy.get("mode")
    if mode == "track":
        if desired_ref is None:
            raise RegistrySyncError(f"registry {name} track policy requires a branch ref")
        branch = short_pin_value("branch", pin.get("value"))
        if desired_ref not in allowed_refs:
            raise RegistrySyncError(f"registry {name} ref {desired_ref!r} is not allowed")
        _git("fetch", "--prune", "origin", f"+{desired_ref}:refs/remotes/origin/{branch}", cwd=path)
        return _git("rev-parse", f"refs/remotes/origin/{branch}", cwd=path)
    if mode != "pinned":
        raise RegistrySyncError(f"registry {name} unsupported update policy: {mode}")
    if pin.get("mode") == "tag":
        if desired_ref is None:
            raise RegistrySyncError(f"registry {name} pinned tag is missing its canonical ref")
        tag = short_pin_value("tag", pin.get("value"))
        if desired_ref not in allowed_refs:
            raise RegistrySyncError(f"registry {name} ref {desired_ref!r} is not allowed")
        return _git("rev-parse", f"refs/tags/{tag}^{{commit}}", cwd=path)
    if pin.get("mode") == "commit":
        commit = str(pin.get("value"))
        try:
            _git("rev-parse", f"{commit}^{{commit}}", cwd=path)
        except RegistrySyncError:
            _git("fetch", "origin", commit, cwd=path)
        return _git("rev-parse", f"{commit}^{{commit}}", cwd=path)
    raise RegistrySyncError(f"registry {name} pinned policy requires tag or commit pinning")


def sync_registry_source(
    *,
    root: str | Path,
    name: str,
    force: bool = False,
    snapshot: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    registry = _load_registry(repo_root, name)
    if snapshot:
        return {
            "registry": name,
            "mode": "snapshot",
            "path": str(_snapshot_path(repo_root, name, snapshot)),
        }

    kind = registry.get("kind")
    path = resolve_registry_root(repo_root, registry)
    update_policy = normalized_update_policy(registry)
    configured_host = extract_git_host(registry.get("url"))
    allowed_hosts = normalized_allowed_hosts(registry)
    if configured_host and configured_host not in allowed_hosts:
        raise RegistrySyncError(f"registry {name} URL host {configured_host!r} is not allowed")
    if kind == "local":
        if path is None or not path.exists():
            raise RegistrySyncError(f"local registry path does not exist: {path}")
        return {"registry": name, "mode": "local", "path": str(path)}
    if kind != "git":
        raise RegistrySyncError(f"unsupported registry kind: {kind}")
    if update_policy.get("mode") == "local-only":
        if path is None or not (path / ".git").exists():
            raise RegistrySyncError(f"local-only registry is not a git checkout: {path}")
        return {"registry": name, "mode": "local-only", "path": str(path)}
    if path is None or path == repo_root:
        raise RegistrySyncError(f"invalid cache target for registry {name}: {path}")

    _prepare_git_cache(repo_root, registry, path, force=force)
    _validate_origin(path, name=name, configured_host=configured_host, allowed_hosts=allowed_hosts)
    _git("fetch", "--prune", "--tags", "origin", cwd=path)
    pin = normalized_pin(registry)
    desired_ref = canonical_pin_ref(pin.get("mode"), pin.get("value"))
    commit = _resolve_target_commit(
        path,
        name=name,
        pin=pin,
        update_policy=update_policy,
        desired_ref=desired_ref,
        allowed_refs=normalized_allowed_refs(registry),
    )
    _git("checkout", "--detach", commit, cwd=path)
    _git("reset", "--hard", commit, cwd=path)
    raw_source_tag = short_pin_value("tag", pin.get("value")) if pin.get("mode") == "tag" else None
    source_tag = raw_source_tag if isinstance(raw_source_tag, str) else None
    write_refresh_state(
        repo_root,
        registry_name=name,
        kind=kind,
        cache_path=path,
        source_commit=commit,
        source_ref=desired_ref,
        source_tag=source_tag,
    )
    return {
        "registry": name,
        "mode": update_policy.get("mode"),
        "path": str(path),
        "commit": commit,
    }


def sync_all_registry_sources(*, root: str | Path, force: bool = False) -> list[dict[str, Any]]:
    repo_root = Path(root).resolve()
    config = load_registry_config(repo_root)
    return [
        sync_registry_source(root=repo_root, name=str(registry.get("name")), force=force)
        for registry in config.get("registries") or []
        if registry.get("enabled", True)
    ]


def mirror_registry(
    *, root: str | Path, remote: str, branch: str | None = None, dry_run: bool = False
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    _git("remote", "get-url", remote, cwd=repo_root)
    if _git("status", "--short", cwd=repo_root):
        raise RegistrySyncError("source-of-truth repo is dirty; commit changes before mirroring")
    selected_branch = branch or _git("branch", "--show-current", cwd=repo_root)
    if not selected_branch:
        raise RegistrySyncError("could not determine branch to mirror")
    commands = [
        ["git", "push", remote, f"refs/heads/{selected_branch}:refs/heads/{selected_branch}"],
        ["git", "push", remote, "--tags"],
    ]
    if not dry_run:
        for command in commands:
            _git(*command[1:], cwd=repo_root)
    return {
        "ok": True,
        "remote": remote,
        "branch": selected_branch,
        "dry_run": dry_run,
        "commands": commands,
    }


__all__ = [
    "RegistrySyncError",
    "mirror_registry",
    "sync_all_registry_sources",
    "sync_registry_source",
]
