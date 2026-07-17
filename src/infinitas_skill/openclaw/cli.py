"""Maintained CLI surface for the canonical OpenClaw runtime."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, cast

from infinitas_skill.root import ROOT
from infinitas_skill.skills.openclaw import (
    OpenClawBridgeError,
    derive_registry_meta,
    export_release_to_directory,
    parse_skill_frontmatter,
    resolve_ai_release,
    resolve_skill_dir,
    scaffold_imported_skill,
)

from .plugins import normalize_plugin_capabilities
from .runtime_model import build_openclaw_runtime_model
from .skill_contract import OpenClawSkillContractError, load_openclaw_skill_contract
from .workspace import resolve_openclaw_skill_dirs

OPENCLAW_TOP_LEVEL_HELP = "OpenClaw runtime tools"
OPENCLAW_PARSER_DESCRIPTION = "Inspect and validate the maintained OpenClaw runtime contract"


def _print_payload(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_openclaw_profile(*, as_json: bool = False) -> int:
    payload = build_openclaw_runtime_model(ROOT)
    _print_payload(payload, as_json=as_json)
    return 0


def run_openclaw_workspace_resolve(
    *,
    workspace_root: str,
    home: str | None = None,
    as_json: bool = False,
) -> int:
    workspace_path = Path(workspace_root).resolve()
    home_path = Path(home).resolve() if isinstance(home, str) and home.strip() else None
    dirs = resolve_openclaw_skill_dirs(workspace_path, home=home_path, root=ROOT)
    payload = {
        "workspace_root": str(workspace_path),
        "skill_dirs": [str(path.resolve()) for path in dirs],
    }
    _print_payload(payload, as_json=as_json)
    return 0


def run_openclaw_skill_validate(*, skill_dir: str, as_json: bool = False) -> int:
    try:
        contract = load_openclaw_skill_contract(Path(skill_dir).resolve())
    except OpenClawSkillContractError as exc:
        if as_json:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    payload = {
        "ok": True,
        "contract": contract,
    }
    _print_payload(payload, as_json=as_json)
    return 0


def run_openclaw_skill_import(
    *,
    source_path: str,
    owner: str,
    publisher: str | None,
    mode: str,
    force: bool,
    root: str | Path = ROOT,
    as_json: bool = False,
) -> int:
    repo_root = Path(root).resolve()
    try:
        source_dir = resolve_skill_dir(source_path)
        meta = derive_registry_meta(
            parse_skill_frontmatter(source_dir / "SKILL.md"),
            owner=owner,
            publisher=publisher,
        )
        target_dir = repo_root / "skills" / "incubating" / str(meta["name"])
        payload = {
            "ok": True,
            "state": "planned" if mode == "confirm" else "imported",
            "source_dir": str(source_dir),
            "target_dir": str(target_dir),
            "name": meta["name"],
            "qualified_name": meta.get("qualified_name") or meta["name"],
            "owner": meta["owner"],
            "publisher": meta.get("publisher"),
            "mode": mode,
            "force": force,
        }
        if mode == "confirm":
            payload["next_step"] = "run-import"
        else:
            result = scaffold_imported_skill(source_dir, target_dir, meta, force=force)
            payload["files"] = result["files"]
            payload["next_step"] = "validate-imported-skill"
    except OpenClawBridgeError as exc:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "import-openclaw-failed",
            "message": str(exc),
        }
        _print_payload(payload, as_json=as_json)
        return 1
    _print_payload(payload, as_json=as_json)
    return 0


def run_openclaw_skill_export(
    *,
    requested_name: str,
    out_dir: str,
    requested_version: str | None,
    mode: str,
    force: bool,
    root: str | Path = ROOT,
    as_json: bool = False,
) -> int:
    repo_root = Path(root).resolve()
    try:
        selected, resolved_version, version_entry = resolve_ai_release(
            repo_root, requested_name, requested_version=requested_version
        )
        export_dir = (
            Path(out_dir).expanduser() / str(selected.get("name") or requested_name)
        ).resolve()
        manifest_path = (repo_root / str(version_entry["manifest_path"])).resolve()
        payload = {
            "ok": True,
            "state": "planned" if mode == "confirm" else "exported",
            "name": selected.get("name"),
            "qualified_name": selected.get("qualified_name") or selected.get("name"),
            "resolved_version": resolved_version,
            "manifest_path": str(manifest_path),
            "bundle_path": str((repo_root / str(version_entry["bundle_path"])).resolve()),
            "export_dir": str(export_dir),
            "mode": mode,
            "force": force,
            "suggested_publish_command": ["clawhub", "publish", str(export_dir)],
        }
        target = export_dir
        if mode == "confirm":
            target = repo_root / ".tmp-openclaw-export-preview" / str(selected.get("name"))
        result = export_release_to_directory(
            repo_root,
            manifest_path,
            target,
            force=True if mode == "confirm" else force,
            public_ready=True,
        )
        payload["public_ready"] = result["public_ready"]
        payload["validation_errors"] = result["validation_errors"]
        if mode == "confirm":
            shutil.rmtree(target.parent, ignore_errors=True)
            payload["next_step"] = "run-export"
        else:
            payload["files"] = result["files"]
            payload["next_step"] = "review-or-publish-manually"
    except OpenClawBridgeError as exc:
        payload = {
            "ok": False,
            "state": "failed",
            "error_code": "export-openclaw-failed",
            "message": str(exc),
        }
        _print_payload(payload, as_json=as_json)
        return 1
    _print_payload(payload, as_json=as_json)
    return 0


def _load_plugin_payload(path: Path) -> dict[Any, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("plugin_capabilities"), dict):
        return cast(dict[Any, Any], payload["plugin_capabilities"])
    if isinstance(payload.get("capabilities"), dict):
        return cast(dict[Any, Any], payload["capabilities"])
    return cast(dict[Any, Any], payload) if isinstance(payload, dict) else {}


def run_openclaw_plugin_inspect(*, plugin_path: str, as_json: bool = False) -> int:
    path = Path(plugin_path).resolve()
    payload = {
        "ok": True,
        "path": str(path),
        "plugin_capabilities": normalize_plugin_capabilities(_load_plugin_payload(path)),
    }
    _print_payload(payload, as_json=as_json)
    return 0


def configure_openclaw_profile_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    return parser


def build_openclaw_profile_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Inspect the canonical OpenClaw runtime profile",
    )
    return configure_openclaw_profile_parser(parser)


def configure_openclaw_workspace_resolve_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("workspace_root", help="Workspace root to resolve skill directories for")
    parser.add_argument("--home", help="Override the home directory used for ~/ expansion")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    return parser


def build_openclaw_workspace_resolve_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Resolve OpenClaw skill-directory precedence for one workspace",
    )
    return configure_openclaw_workspace_resolve_parser(parser)


def configure_openclaw_skill_validate_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument(
        "skill_dir",
        help="Skill directory to validate against the OpenClaw contract",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    return parser


def configure_openclaw_skill_import_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("source_path")
    parser.add_argument("--owner", default=os.environ.get("USER", "unknown"))
    parser.add_argument("--publisher")
    parser.add_argument("--mode", choices=("auto", "confirm"), default="auto")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    return parser


def configure_openclaw_skill_export_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("requested_name")
    parser.add_argument("--out", required=True)
    parser.add_argument("--version")
    parser.add_argument("--mode", choices=("auto", "confirm"), default="auto")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    return parser


def build_openclaw_skill_validate_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Validate one skill directory against the OpenClaw runtime contract",
    )
    return configure_openclaw_skill_validate_parser(parser)


def configure_openclaw_plugin_inspect_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("plugin_path", help="Plugin JSON payload to inspect")
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    return parser


def build_openclaw_plugin_inspect_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Inspect and normalize declared OpenClaw plugin capabilities",
    )
    return configure_openclaw_plugin_inspect_parser(parser)


def configure_openclaw_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(dest="openclaw_command")

    profile = subparsers.add_parser(
        "profile",
        help="Inspect the canonical OpenClaw runtime profile",
        description="Inspect the canonical OpenClaw runtime profile",
    )
    configure_openclaw_profile_parser(profile)
    profile.set_defaults(_handler=lambda args: run_openclaw_profile(as_json=args.json))

    workspace = subparsers.add_parser(
        "workspace",
        help="OpenClaw workspace resolution tools",
        description="OpenClaw workspace resolution tools",
    )
    workspace_sub = workspace.add_subparsers(dest="openclaw_workspace_command")
    workspace_resolve = workspace_sub.add_parser(
        "resolve",
        help="Resolve OpenClaw skill-directory precedence for one workspace",
        description="Resolve OpenClaw skill-directory precedence for one workspace",
    )
    configure_openclaw_workspace_resolve_parser(workspace_resolve)
    workspace_resolve.set_defaults(
        _handler=lambda args: run_openclaw_workspace_resolve(
            workspace_root=args.workspace_root,
            home=args.home,
            as_json=args.json,
        )
    )

    skill = subparsers.add_parser(
        "skill",
        help="OpenClaw skill validation tools",
        description="OpenClaw skill validation tools",
    )
    skill_sub = skill.add_subparsers(dest="openclaw_skill_command")
    skill_validate = skill_sub.add_parser(
        "validate",
        help="Validate one skill directory against the OpenClaw runtime contract",
        description="Validate one skill directory against the OpenClaw runtime contract",
    )
    configure_openclaw_skill_validate_parser(skill_validate)
    skill_validate.set_defaults(
        _handler=lambda args: run_openclaw_skill_validate(
            skill_dir=args.skill_dir,
            as_json=args.json,
        )
    )
    skill_import = skill_sub.add_parser("import", help="Import a rendered OpenClaw skill")
    configure_openclaw_skill_import_parser(skill_import)
    skill_import.set_defaults(
        _handler=lambda args: run_openclaw_skill_import(
            source_path=args.source_path,
            owner=args.owner,
            publisher=args.publisher,
            mode=args.mode,
            force=args.force,
            root=args.repo_root,
            as_json=args.json,
        )
    )
    skill_export = skill_sub.add_parser("export", help="Export an immutable OpenClaw release")
    configure_openclaw_skill_export_parser(skill_export)
    skill_export.set_defaults(
        _handler=lambda args: run_openclaw_skill_export(
            requested_name=args.requested_name,
            out_dir=args.out,
            requested_version=args.version,
            mode=args.mode,
            force=args.force,
            root=args.repo_root,
            as_json=args.json,
        )
    )

    plugin = subparsers.add_parser(
        "plugin",
        help="OpenClaw plugin capability tools",
        description="OpenClaw plugin capability tools",
    )
    plugin_sub = plugin.add_subparsers(dest="openclaw_plugin_command")
    plugin_inspect = plugin_sub.add_parser(
        "inspect",
        help="Inspect and normalize declared OpenClaw plugin capabilities",
        description="Inspect and normalize declared OpenClaw plugin capabilities",
    )
    configure_openclaw_plugin_inspect_parser(plugin_inspect)
    plugin_inspect.set_defaults(
        _handler=lambda args: run_openclaw_plugin_inspect(
            plugin_path=args.plugin_path,
            as_json=args.json,
        )
    )
    return parser


def build_openclaw_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=OPENCLAW_PARSER_DESCRIPTION,
    )
    return configure_openclaw_parser(parser)


__all__ = [
    "OPENCLAW_PARSER_DESCRIPTION",
    "OPENCLAW_TOP_LEVEL_HELP",
    "build_openclaw_parser",
    "build_openclaw_plugin_inspect_parser",
    "build_openclaw_profile_parser",
    "build_openclaw_skill_validate_parser",
    "build_openclaw_workspace_resolve_parser",
    "configure_openclaw_parser",
    "run_openclaw_plugin_inspect",
    "run_openclaw_profile",
    "run_openclaw_skill_validate",
    "run_openclaw_skill_import",
    "run_openclaw_skill_export",
    "run_openclaw_workspace_resolve",
]
