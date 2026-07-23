from __future__ import annotations

import argparse

from infinitas_skill.install.exact import configure_install_exact_parser, run_install_exact
from infinitas_skill.install.hosted_share import (
    configure_install_from_share_parser,
    run_install_from_share_command,
)
from infinitas_skill.install.integrity import (
    configure_install_list_parser,
    configure_install_repair_parser,
    configure_install_report_parser,
    configure_install_verify_parser,
    run_install_repair,
    run_install_report,
    run_install_verify,
)
from infinitas_skill.install.planning import (
    configure_check_install_target_parser,
    configure_resolve_install_plan_parser,
    run_check_install_target,
    run_resolve_install_plan,
)
from infinitas_skill.install.resolve import (
    configure_install_by_name_parser,
    configure_install_resolve_skill_parser,
    run_install_by_name,
    run_install_resolve_skill,
)
from infinitas_skill.install.rollback import (
    configure_install_rollback_parser,
    run_install_rollback,
)
from infinitas_skill.install.switch import configure_install_switch_parser, run_install_switch
from infinitas_skill.install.sync import configure_install_sync_parser, run_install_sync
from infinitas_skill.install.update import (
    configure_install_check_update_parser,
    run_install_check_update,
)
from infinitas_skill.install.upgrade import (
    configure_install_upgrade_parser,
    run_install_upgrade,
)


def _configure_from_share_command(subparsers: argparse._SubParsersAction) -> None:
    from_share = subparsers.add_parser(
        "from-share",
        help="Resolve and install an immutable hosted share",
        description="Resolve and install an immutable hosted share",
    )
    configure_install_from_share_parser(from_share)
    from_share.set_defaults(
        _handler=lambda args: run_install_from_share_command(
            root=args.repo_root,
            resolve_url=args.resolve_url,
            target_dir=args.target_dir,
            password_env=args.password_env,
            secret_env=args.secret_env,
            force=args.force,
            no_deps=args.no_deps,
            as_json=args.json,
        )
    )


def _configure_planning_and_resolution(subparsers: argparse._SubParsersAction) -> None:
    resolve_plan = subparsers.add_parser(
        "resolve-plan",
        help="Resolve an install or sync dependency plan",
        description="Resolve an install or sync dependency plan",
    )
    configure_resolve_install_plan_parser(resolve_plan)
    resolve_plan.set_defaults(
        _handler=lambda args: run_resolve_install_plan(
            skill_dir=args.skill_dir,
            registry_entry_json=args.registry_entry_json,
            target_dir=args.target_dir,
            source_registry=args.source_registry,
            source_json=args.source_json,
            mode=args.mode,
            as_json=args.json,
        )
    )

    check_target = subparsers.add_parser(
        "check-target",
        help="Check whether an install target is dependency-safe",
        description="Check whether an install target is dependency-safe",
    )
    configure_check_install_target_parser(check_target)
    check_target.set_defaults(
        _handler=lambda args: run_check_install_target(
            skill_dir=args.skill_dir,
            target_dir=args.target_dir,
            source_registry=args.source_registry,
            source_json=args.source_json,
            mode=args.mode,
            as_json=args.json,
        )
    )

    resolve_skill = subparsers.add_parser(
        "resolve-skill",
        help="Resolve one install candidate from the discovery index",
        description="Resolve one install candidate from the discovery index",
    )
    configure_install_resolve_skill_parser(resolve_skill)
    resolve_skill.set_defaults(
        _handler=lambda args: run_install_resolve_skill(
            root=args.repo_root,
            query=args.query,
            target_agent=args.target_agent,
            as_json=args.json,
        )
    )

    exact = subparsers.add_parser(
        "exact",
        help="Install one exact released skill and apply its dependency plan",
        description="Install one exact released skill and apply its dependency plan",
    )
    configure_install_exact_parser(exact)
    exact.set_defaults(
        _handler=lambda args: run_install_exact(
            root=args.repo_root,
            name=args.name,
            target_dir=args.target_dir,
            requested_version=args.version,
            source_registry=args.registry,
            snapshot=args.snapshot,
            force=args.force,
            no_deps=args.no_deps,
            as_json=args.json,
        )
    )

    _configure_from_share_command(subparsers)

    by_name = subparsers.add_parser(
        "by-name",
        help="Resolve and install one released skill by discovery-first name lookup",
        description="Resolve and install one released skill by discovery-first name lookup",
    )
    configure_install_by_name_parser(by_name)
    by_name.set_defaults(
        _handler=lambda args: run_install_by_name(
            root=args.repo_root,
            query=args.query,
            target_dir=args.target_dir,
            requested_version=args.version,
            target_agent=args.target_agent,
            mode=args.mode,
            as_json=args.json,
        )
    )


def _configure_sync_and_mutation(subparsers: argparse._SubParsersAction) -> None:
    sync = subparsers.add_parser(
        "sync",
        help="Sync one installed skill to the latest releasable state from its source",
        description="Sync one installed skill to the latest releasable state from its source",
    )
    configure_install_sync_parser(sync)
    sync.set_defaults(
        _handler=lambda args: run_install_sync(
            root=args.repo_root,
            installed_name=args.installed_name,
            target_dir=args.target_dir,
            force=args.force,
            as_json=args.json,
        )
    )

    check_update = subparsers.add_parser(
        "check-update",
        help="Check whether an installed skill has a newer same-registry release",
        description="Check whether an installed skill has a newer same-registry release",
    )
    configure_install_check_update_parser(check_update)
    check_update.set_defaults(
        _handler=lambda args: run_install_check_update(
            root=args.repo_root,
            installed_name=args.installed_name,
            target_dir=args.target_dir,
            as_json=args.json,
        )
    )

    switch = subparsers.add_parser(
        "switch",
        help="Switch one installed skill to another releasable source revision",
        description="Switch one installed skill to another releasable source revision",
    )
    configure_install_switch_parser(switch)
    switch.set_defaults(
        _handler=lambda args: run_install_switch(
            root=args.repo_root,
            installed_name=args.installed_name,
            target_dir=args.target_dir,
            requested_version=args.to_version,
            to_active=args.to_active,
            source_registry=args.registry,
            qualified_name=args.qualified_name,
            force=args.force,
            as_json=args.json,
        )
    )

    rollback = subparsers.add_parser(
        "rollback",
        help="Rollback one installed skill to a recorded prior manifest entry",
        description="Rollback one installed skill to a recorded prior manifest entry",
    )
    configure_install_rollback_parser(rollback)
    rollback.set_defaults(
        _handler=lambda args: run_install_rollback(
            root=args.repo_root,
            installed_name=args.installed_name,
            target_dir=args.target_dir,
            steps=args.steps,
            force=args.force,
            as_json=args.json,
        )
    )

    upgrade = subparsers.add_parser(
        "upgrade",
        help="Upgrade one installed skill in place from the recorded source registry",
        description="Upgrade one installed skill in place from the recorded source registry",
    )
    configure_install_upgrade_parser(upgrade)
    upgrade.set_defaults(
        _handler=lambda args: run_install_upgrade(
            root=args.repo_root,
            installed_name=args.installed_name,
            target_dir=args.target_dir,
            requested_version=args.to_version,
            source_registry=args.registry,
            mode=args.mode,
            force=args.force,
            as_json=args.json,
        )
    )


def _configure_integrity_commands(subparsers: argparse._SubParsersAction) -> None:
    list_installed = subparsers.add_parser("list", help="List installed skills and integrity state")
    configure_install_list_parser(list_installed)
    list_installed.set_defaults(
        _handler=lambda args: run_install_report(
            root=args.repo_root,
            target_dir=args.target_dir,
            as_json=args.json,
        )
    )

    report = subparsers.add_parser("report", help="Report or refresh installed integrity state")
    configure_install_report_parser(report)
    report.set_defaults(
        _handler=lambda args: run_install_report(
            root=args.repo_root,
            target_dir=args.target_dir,
            refresh=args.refresh,
            as_json=args.json,
        )
    )

    verify = subparsers.add_parser("verify", help="Verify one installed skill")
    configure_install_verify_parser(verify)
    verify.set_defaults(
        _handler=lambda args: run_install_verify(
            root=args.repo_root,
            installed_name=args.installed_name,
            target_dir=args.target_dir,
            as_json=args.json,
        )
    )

    repair = subparsers.add_parser("repair", help="Repair one drifted installed skill")
    configure_install_repair_parser(repair)
    repair.set_defaults(
        _handler=lambda args: run_install_repair(
            root=args.repo_root,
            installed_name=args.installed_name,
            target_dir=args.target_dir,
            as_json=args.json,
        )
    )


def configure_install_cli(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(dest="install_command")
    _configure_planning_and_resolution(subparsers)
    _configure_sync_and_mutation(subparsers)
    _configure_integrity_commands(subparsers)
    return parser
