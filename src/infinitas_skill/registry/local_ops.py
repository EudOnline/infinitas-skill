"""Repository-local registry source operations."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import httpx

from infinitas_skill.install.registry_source_primitives import (
    resolve_registry_root,
    short_pin_value,
)
from infinitas_skill.install.registry_sources import (
    find_registry,
    load_registry_config,
    registry_identity,
    registry_is_resolution_candidate,
    validate_registry_config,
)
from infinitas_skill.registry.refresh_state import evaluate_refresh_status
from infinitas_skill.registry.snapshot import create_snapshot, snapshot_catalog_summary
from infinitas_skill.registry.sync import (
    RegistrySyncError,
    mirror_registry,
    sync_all_registry_sources,
    sync_registry_source,
)

_REGISTRY_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _emit(payload: dict, *, as_json: bool) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if as_json else None))
    return 0


def _load_validated(root: Path) -> tuple[dict, list[dict]]:
    config = load_registry_config(root)
    errors = validate_registry_config(root, config)
    if errors:
        raise ValueError("invalid registry-sources.json: " + "; ".join(errors))
    return config, list(config.get("registries") or [])


def run_registry_sources_check(*, root: str | Path, as_json: bool = False) -> int:
    repo_root = Path(root).resolve()
    try:
        _config, registries = _load_validated(repo_root)
    except ValueError as exc:
        return _emit({"ok": False, "errors": [str(exc)]}, as_json=as_json) or 1
    return _emit(
        {"ok": True, "root": str(repo_root), "registry_count": len(registries)},
        as_json=as_json,
    )


def _source_payload(root: Path, registry: dict) -> dict:
    identity = registry_identity(root, registry)
    pin_mode = identity.get("registry_pin_mode")
    snapshot_summary = snapshot_catalog_summary(root, str(registry.get("name")))
    return {
        "name": registry.get("name"),
        "kind": registry.get("kind"),
        "url": registry.get("url"),
        "enabled": registry.get("enabled", True),
        "priority": registry.get("priority"),
        "trust": registry.get("trust"),
        "resolved_root": str(resolve_registry_root(root, registry)),
        "pin_mode": pin_mode,
        "pin_value": short_pin_value(pin_mode, identity.get("registry_pin_value"))
        if pin_mode
        else None,
        "update_mode": identity.get("registry_update_mode"),
        "resolver_candidate": registry_is_resolution_candidate(registry),
        "snapshot_count": snapshot_summary.get("snapshot_count"),
        "latest_snapshot": (snapshot_summary.get("latest_snapshot") or {}).get("snapshot_id"),
    }


def run_registry_sources_list(*, root: str | Path, as_json: bool = False) -> int:
    repo_root = Path(root).resolve()
    try:
        config, registries = _load_validated(repo_root)
    except ValueError as exc:
        return _emit({"ok": False, "errors": [str(exc)]}, as_json=as_json) or 1
    return _emit(
        {
            "ok": True,
            "default_registry": config.get("default_registry"),
            "registries": [_source_payload(repo_root, registry) for registry in registries],
        },
        as_json=as_json,
    )


def _read_local_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "$schema": "../schemas/registry-sources.schema.json",
            "default_registry": "",
            "registries": [],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write_config_atomically(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _write_text_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        path.chmod(0o644)
    finally:
        temp_path.unlink(missing_ok=True)


def _prepare_http_registry_source(
    *,
    root: Path,
    name: str,
    base_url: str,
    token_env: str,
    set_default: bool = False,
) -> tuple[Path, dict[str, Any], dict[str, Any], bool]:
    if not _REGISTRY_NAME_RE.fullmatch(name):
        raise ValueError("registry name must use lowercase kebab-case")
    if not _ENV_NAME_RE.fullmatch(token_env):
        raise ValueError("token environment variable name is invalid")
    config_path = root / "config" / "registry-sources.json"
    config = _read_local_config(config_path)
    registries = config.get("registries")
    if not isinstance(registries, list):
        raise ValueError("registries must be an array")
    entry = {
        "name": name,
        "kind": "http",
        "base_url": base_url.rstrip("/"),
        "enabled": True,
        "priority": 100,
        "trust": "private",
        "auth": {"mode": "token", "env": token_env},
    }
    existing = next(
        (item for item in registries if isinstance(item, dict) and item.get("name") == name),
        None,
    )
    if existing is not None and existing != entry:
        raise ValueError(f"registry {name!r} already exists with different configuration")
    changed = existing is None or (set_default and config.get("default_registry") != name)
    if existing is None:
        registries.append(entry)
    if set_default or not config.get("default_registry"):
        config["default_registry"] = name
    errors = validate_registry_config(root, config)
    if errors:
        raise ValueError("invalid registry-sources.json: " + "; ".join(errors))
    return config_path, config, entry, changed


def add_http_registry_source(
    *,
    root: str | Path,
    name: str,
    base_url: str,
    token_env: str,
    set_default: bool = False,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    config_path, config, entry, changed = _prepare_http_registry_source(
        root=repo_root,
        name=name,
        base_url=base_url,
        token_env=token_env,
        set_default=set_default,
    )
    if changed:
        _write_config_atomically(config_path, config)
    return {
        "ok": True,
        "changed": changed,
        "name": name,
        "base_url": entry["base_url"],
        "token_env": token_env,
        "default_registry": config.get("default_registry"),
        "path": str(config_path),
    }


def run_registry_sources_add_http(
    *,
    root: str | Path,
    name: str,
    base_url: str,
    token_env: str,
    set_default: bool = False,
    as_json: bool = False,
) -> int:
    try:
        payload = add_http_registry_source(
            root=root,
            name=name,
            base_url=base_url,
            token_env=token_env,
            set_default=set_default,
        )
    except ValueError as exc:
        return _emit({"ok": False, "message": str(exc)}, as_json=as_json) or 1
    return _emit(payload, as_json=as_json)


def _trust_files(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("registry trust bootstrap response is invalid")
    signing = payload.get("signing")
    integrity = payload.get("install_integrity_policy")
    allowed = payload.get("allowed_signers")
    if not isinstance(signing, dict) or not isinstance(integrity, dict):
        raise ValueError("registry trust bootstrap policies are invalid")
    if not isinstance(allowed, str) or not allowed.strip():
        raise ValueError("registry trust bootstrap has no allowed signers")
    return {
        "signing.json": json.dumps(signing, ensure_ascii=False, indent=2) + "\n",
        "allowed_signers": allowed.rstrip() + "\n",
        "install-integrity-policy.json": json.dumps(integrity, ensure_ascii=False, indent=2) + "\n",
    }


def _preflight_trust_files(root: Path, files: dict[str, str], *, force: bool) -> bool:
    changed = False
    for name, content in files.items():
        path = root / "config" / name
        if not path.exists():
            changed = True
            continue
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            continue
        if not force:
            raise ValueError(f"trust file {path} already exists with different content")
        changed = True
    return changed


def run_registry_bootstrap(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        return (
            _emit(
                {"ok": False, "message": f"missing token in environment {args.token_env}"},
                as_json=args.json,
            )
            or 1
        )
    try:
        config_path, config, entry, source_changed = _prepare_http_registry_source(
            root=root,
            name=args.name,
            base_url=args.base_url,
            token_env=args.token_env,
            set_default=args.set_default,
        )
        response = httpx.get(
            f"{entry['base_url']}/trust-bootstrap.json",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0,
        )
        if response.status_code >= 400:
            raise ValueError(f"registry trust endpoint returned HTTP {response.status_code}")
        files = _trust_files(response.json())
        trust_changed = _preflight_trust_files(root, files, force=args.force_trust)
        for name, content in files.items():
            path = root / "config" / name
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                _write_text_atomically(path, content)
        if source_changed:
            _write_config_atomically(config_path, config)
    except (OSError, ValueError, httpx.HTTPError) as exc:
        return _emit({"ok": False, "message": str(exc)}, as_json=args.json) or 1
    return _emit(
        {
            "ok": True,
            "name": args.name,
            "base_url": entry["base_url"],
            "token_env": args.token_env,
            "source_changed": source_changed,
            "trust_changed": trust_changed,
            "config_path": str(config_path),
            "trust_paths": [str(root / "config" / name) for name in sorted(files)],
        },
        as_json=args.json,
    )


def _find_source(root: Path, registry_name: str) -> dict:
    config, _registries = _load_validated(root)
    registry = find_registry(config, registry_name)
    if registry is None:
        raise ValueError(f"unknown registry: {registry_name}")
    return registry


def run_registry_sources_status(
    *, root: str | Path, registry_name: str, as_json: bool = False
) -> int:
    repo_root = Path(root).resolve()
    try:
        payload = evaluate_refresh_status(repo_root, _find_source(repo_root, registry_name))
    except ValueError as exc:
        return _emit({"ok": False, "message": str(exc)}, as_json=as_json) or 1
    return _emit(payload, as_json=as_json)


def run_registry_sources_snapshot(
    *,
    root: str | Path,
    registry_name: str,
    snapshot_id: str | None = None,
    as_json: bool = False,
) -> int:
    repo_root = Path(root).resolve()
    try:
        payload = create_snapshot(
            repo_root,
            _find_source(repo_root, registry_name),
            snapshot_id=snapshot_id,
        )
    except ValueError as exc:
        return _emit({"ok": False, "message": str(exc)}, as_json=as_json) or 1
    return _emit(payload, as_json=as_json)


def run_registry_sources_sync(args: argparse.Namespace) -> int:
    try:
        payload = sync_registry_source(
            root=args.repo_root,
            name=args.registry_name,
            force=args.force,
            snapshot=args.snapshot,
        )
    except RegistrySyncError as exc:
        return _emit({"ok": False, "message": str(exc)}, as_json=args.json) or 1
    return _emit(payload, as_json=args.json)


def run_registry_sources_sync_all(args: argparse.Namespace) -> int:
    try:
        payload = sync_all_registry_sources(root=args.repo_root, force=args.force)
    except RegistrySyncError as exc:
        return _emit({"ok": False, "message": str(exc)}, as_json=args.json) or 1
    return _emit({"ok": True, "registries": payload}, as_json=args.json)


def run_registry_mirror(args: argparse.Namespace) -> int:
    try:
        payload = mirror_registry(
            root=args.repo_root,
            remote=args.remote,
            branch=args.branch,
            dry_run=args.dry_run,
        )
    except RegistrySyncError as exc:
        return _emit({"ok": False, "message": str(exc)}, as_json=args.json) or 1
    return _emit(payload, as_json=args.json)


def configure_registry_sources_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--repo-root", default=".")
    subparsers = parser.add_subparsers(dest="registry_sources_command")
    for name, help_text, handler in (
        ("check", "Validate registry source configuration", run_registry_sources_check),
        ("list", "List configured registry sources", run_registry_sources_list),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--json", action="store_true")
        command.set_defaults(
            _handler=lambda args, selected=handler: selected(
                root=args.repo_root,
                as_json=args.json,
            )
        )

    status = subparsers.add_parser("status", help="Show registry refresh status")
    status.add_argument("registry_name")
    status.add_argument("--json", action="store_true")
    status.set_defaults(
        _handler=lambda args: run_registry_sources_status(
            root=args.repo_root,
            registry_name=args.registry_name,
            as_json=args.json,
        )
    )
    snapshot = subparsers.add_parser("snapshot", help="Create an immutable registry snapshot")
    snapshot.add_argument("registry_name")
    snapshot.add_argument("--snapshot-id")
    snapshot.add_argument("--json", action="store_true")
    snapshot.set_defaults(
        _handler=lambda args: run_registry_sources_snapshot(
            root=args.repo_root,
            registry_name=args.registry_name,
            snapshot_id=args.snapshot_id,
            as_json=args.json,
        )
    )
    add_http = subparsers.add_parser("add-http", help="Add a private Hosted Registry source")
    add_http.add_argument("name", help="Registry source name in lowercase kebab-case")
    add_http.add_argument("base_url", help="Hosted catalog base URL")
    add_http.add_argument(
        "--token-env",
        default="INFINITAS_REGISTRY_TOKEN",
        help="Environment variable containing the read token",
    )
    add_http.add_argument("--set-default", action="store_true")
    add_http.add_argument("--json", action="store_true")
    add_http.set_defaults(
        _handler=lambda args: run_registry_sources_add_http(
            root=args.repo_root,
            name=args.name,
            base_url=args.base_url,
            token_env=args.token_env,
            set_default=args.set_default,
            as_json=args.json,
        )
    )
    sync = subparsers.add_parser("sync", help="Synchronize one registry source")
    sync.add_argument("registry_name")
    sync.add_argument("--force", action="store_true")
    sync.add_argument("--snapshot")
    sync.add_argument("--json", action="store_true")
    sync.set_defaults(_handler=run_registry_sources_sync)

    sync_all = subparsers.add_parser("sync-all", help="Synchronize all enabled registry sources")
    sync_all.add_argument("--force", action="store_true")
    sync_all.add_argument("--json", action="store_true")
    sync_all.set_defaults(_handler=run_registry_sources_sync_all)

    mirror = subparsers.add_parser("mirror", help="Push a one-way repository mirror")
    mirror.add_argument("--remote", required=True)
    mirror.add_argument("--branch")
    mirror.add_argument("--dry-run", action="store_true")
    mirror.add_argument("--json", action="store_true")
    mirror.set_defaults(_handler=run_registry_mirror)
    return parser


__all__ = ["configure_registry_sources_parser"]
