"""CLI parser configuration for install workflows.

This module contains all the argparse parser configuration and builder
functions for the install subcommands.
"""
from __future__ import annotations

import argparse


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


def configure_install_sync_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the installed skill")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass stale or never-verified readiness gates after drift checks",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_sync_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Sync one installed skill to the latest releasable state from its source",
    )
    return configure_install_sync_parser(parser)


def configure_install_switch_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the installed skill")
    parser.add_argument("--to-version", default=None, help="Switch to an exact released version")
    parser.add_argument(
        "--to-active",
        action="store_true",
        help="Switch to the currently resolved active source instead of an exact version",
    )
    parser.add_argument("--registry", default=None, help="Optional source registry override")
    parser.add_argument("--qualified-name", default=None, help="Optional qualified_name override")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass stale or never-verified readiness gates after drift checks",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_switch_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Switch one installed skill to another releasable source revision",
    )
    return configure_install_switch_parser(parser)


def configure_install_rollback_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the installed skill")
    parser.add_argument(
        "--steps",
        type=int,
        default=1,
        help="How many history entries to walk back",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass stale or never-verified readiness gates after drift checks",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_rollback_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Rollback one installed skill to a recorded prior manifest entry",
    )
    return configure_install_rollback_parser(parser)


def configure_install_resolve_skill_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("query", help="Skill name or qualified_name to resolve")
    parser.add_argument("--target-agent", default=None, help="Optional target runtime/agent")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_resolve_skill_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Resolve one install candidate from the discovery index",
    )
    return configure_install_resolve_skill_parser(parser)


def configure_install_by_name_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("query", help="Skill name or qualified_name to install")
    parser.add_argument("target_dir", help="Target directory for the installed skill")
    parser.add_argument("--version", default=None, help="Optional released version override")
    parser.add_argument("--target-agent", default=None, help="Optional target runtime/agent")
    parser.add_argument(
        "--mode",
        choices=("auto", "confirm"),
        default="auto",
        help="Whether to install immediately or only confirm the plan",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def configure_install_check_update_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the install manifest")
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_check_update_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Check whether an installed skill has a newer same-registry release",
    )
    return configure_install_check_update_parser(parser)


def configure_install_upgrade_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("installed_name", help="Installed skill name or qualified_name")
    parser.add_argument("target_dir", help="Target directory holding the installed skill")
    parser.add_argument("--to-version", default=None, help="Optional released version override")
    parser.add_argument(
        "--registry",
        default=None,
        help="Optional source registry override; cross-source upgrade is rejected",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "confirm"),
        default="auto",
        help="Whether to upgrade immediately or only confirm the plan",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass stale/never-verified readiness gates after drift checks",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing generated catalog artifacts",
    )
    parser.add_argument("--json", action="store_true", help="Emit pretty JSON output")
    return parser


def build_install_upgrade_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Upgrade one installed skill in place from the recorded source registry",
    )
    return configure_install_upgrade_parser(parser)


def build_install_by_name_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Resolve and install one released skill by discovery-first name lookup",
    )
    return configure_install_by_name_parser(parser)


__all__ = [
    "build_install_exact_parser",
    "build_install_by_name_parser",
    "build_install_check_update_parser",
    "build_install_rollback_parser",
    "build_install_resolve_skill_parser",
    "build_install_switch_parser",
    "build_install_sync_parser",
    "build_install_upgrade_parser",
    "configure_install_exact_parser",
    "configure_install_by_name_parser",
    "configure_install_check_update_parser",
    "configure_install_rollback_parser",
    "configure_install_resolve_skill_parser",
    "configure_install_switch_parser",
    "configure_install_sync_parser",
    "configure_install_upgrade_parser",
]
