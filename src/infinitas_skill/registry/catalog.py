"""Catalog build orchestration and CLI registration."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infinitas_skill.install.registry_sources import load_registry_config
from infinitas_skill.registry.catalog_entries import (
    catalog_source_identity,
    collect_distribution_entries,
    collect_skill_entries,
)
from infinitas_skill.registry.catalog_exports import build_catalog_views


def _generated_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalized(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop("generated_at", None)
    return json.dumps(clone, ensure_ascii=False, sort_keys=True)


def build_catalog_payloads(root: str | Path) -> dict[str, dict[str, Any]]:
    repo_root = Path(root).resolve()
    config = load_registry_config(repo_root)
    _source_registry, source_identity = catalog_source_identity(repo_root, config)
    distributions = collect_distribution_entries(repo_root)
    entries = collect_skill_entries(
        repo_root,
        source_identity=source_identity,
        distribution_entries=distributions,
    )
    return build_catalog_views(
        root=repo_root,
        config=config,
        entries=entries,
        distributions=distributions,
        generated_at=_generated_at(),
    )


def _is_current(path: Path, payload: dict[str, Any]) -> bool:
    if not path.exists():
        return False
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return isinstance(existing, dict) and _normalized(existing) == _normalized(payload)


def run_registry_catalog_build(
    *, root: str | Path, check: bool = False, as_json: bool = False
) -> int:
    repo_root = Path(root).resolve()
    catalog_root = repo_root / "catalog"
    catalog_root.mkdir(parents=True, exist_ok=True)
    payloads = build_catalog_payloads(repo_root)
    changed = [
        name for name, payload in payloads.items() if not _is_current(catalog_root / name, payload)
    ]
    if check:
        result = {"ok": not changed, "changed": changed, "catalog_root": str(catalog_root)}
        print(json.dumps(result, ensure_ascii=False, indent=2 if as_json else None))
        return 1 if changed else 0
    for name, payload in payloads.items():
        path = catalog_root / name
        if name not in changed:
            continue
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {"ok": True, "changed": changed, "catalog_root": str(catalog_root)}
    print(json.dumps(result, ensure_ascii=False, indent=2 if as_json else None))
    return 0


def configure_registry_catalog_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(dest="registry_catalog_command")
    build = subparsers.add_parser("build", help="Build generated registry catalog views")
    build.add_argument("--repo-root", default=".")
    build.add_argument("--check", action="store_true")
    build.add_argument("--json", action="store_true")
    build.set_defaults(
        _handler=lambda args: run_registry_catalog_build(
            root=args.repo_root,
            check=args.check,
            as_json=args.json,
        )
    )
    return parser


__all__ = ["build_catalog_payloads", "configure_registry_catalog_parser"]
