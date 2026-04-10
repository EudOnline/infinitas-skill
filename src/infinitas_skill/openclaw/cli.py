"""Maintained CLI surface for the canonical OpenClaw runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from infinitas_skill.root import ROOT

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


def _load_plugin_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("plugin_capabilities"), dict):
        return payload["plugin_capabilities"]
    if isinstance(payload.get("capabilities"), dict):
        return payload["capabilities"]
    return payload if isinstance(payload, dict) else {}


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
    "run_openclaw_workspace_resolve",
]
