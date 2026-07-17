"""Repository-local registry source operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
