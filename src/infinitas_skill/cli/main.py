import argparse

from infinitas_skill.compatibility.checks import (
    configure_platform_contracts_parser,
    run_check_platform_contracts,
)
from infinitas_skill.install.planning import (
    configure_check_install_target_parser,
    configure_resolve_install_plan_parser,
    run_check_install_target,
    run_resolve_install_plan,
)
from infinitas_skill.openclaw.cli import (
    OPENCLAW_PARSER_DESCRIPTION,
    OPENCLAW_TOP_LEVEL_HELP,
    configure_openclaw_parser,
)
from infinitas_skill.policy.cli import (
    POLICY_PARSER_DESCRIPTION,
    POLICY_TOP_LEVEL_HELP,
    configure_policy_parser,
)
from infinitas_skill.registry.cli import (
    REGISTRY_PARSER_DESCRIPTION,
    REGISTRY_TOP_LEVEL_HELP,
    configure_registry_parser,
)
from infinitas_skill.release.cli import (
    RELEASE_PARSER_DESCRIPTION,
    RELEASE_TOP_LEVEL_HELP,
    configure_release_parser,
)
from infinitas_skill.server.ops import (
    SERVER_PARSER_DESCRIPTION,
    SERVER_TOP_LEVEL_HELP,
    configure_server_parser,
)


def _build_compatibility_check_platform_contracts_parser(subparsers):
    parser = subparsers.add_parser(
        'check-platform-contracts',
        help='Check platform contract-watch documents',
        description='Check platform contract-watch documents.',
    )
    configure_platform_contracts_parser(parser)
    parser.set_defaults(
        _handler=lambda args: run_check_platform_contracts(
            max_age_days=args.max_age_days,
            stale_policy=args.stale_policy,
        )
    )


def _build_install_resolve_plan_parser(subparsers):
    parser = subparsers.add_parser(
        'resolve-plan',
        help='Resolve an install or sync dependency plan',
        description='Resolve an install or sync dependency plan',
    )
    configure_resolve_install_plan_parser(parser)
    parser.set_defaults(
        _handler=lambda args: run_resolve_install_plan(
            skill_dir=args.skill_dir,
            registry_entry_json=args.registry_entry_json,
            target_dir=args.target_dir,
            source_registry=args.source_registry,
            source_json=args.source_json,
            mode=args.mode,
            as_json=args.json,
            memory_mode=args.memory_mode,
        )
    )


def _build_install_check_target_parser(subparsers):
    parser = subparsers.add_parser(
        'check-target',
        help='Check whether an install target is dependency-safe',
        description='Check whether an install target is dependency-safe',
    )
    configure_check_install_target_parser(parser)
    parser.set_defaults(
        _handler=lambda args: run_check_install_target(
            skill_dir=args.skill_dir,
            target_dir=args.target_dir,
            source_registry=args.source_registry,
            source_json=args.source_json,
            mode=args.mode,
            as_json=args.json,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='infinitas', description='infinitas project CLI')
    top = parser.add_subparsers(dest='command')

    compatibility = top.add_parser('compatibility', help='Compatibility tools')
    compatibility_sub = compatibility.add_subparsers(dest='compatibility_command')
    _build_compatibility_check_platform_contracts_parser(compatibility_sub)

    release = top.add_parser(
        'release',
        help=RELEASE_TOP_LEVEL_HELP,
        description=RELEASE_PARSER_DESCRIPTION,
    )
    configure_release_parser(release)

    install = top.add_parser('install', help='Install planning tools')
    install_sub = install.add_subparsers(dest='install_command')
    _build_install_resolve_plan_parser(install_sub)
    _build_install_check_target_parser(install_sub)

    openclaw = top.add_parser(
        'openclaw',
        help=OPENCLAW_TOP_LEVEL_HELP,
        description=OPENCLAW_PARSER_DESCRIPTION,
    )
    configure_openclaw_parser(openclaw)

    registry = top.add_parser(
        'registry',
        help=REGISTRY_TOP_LEVEL_HELP,
        description=REGISTRY_PARSER_DESCRIPTION,
    )
    configure_registry_parser(registry)

    policy = top.add_parser(
        'policy',
        help=POLICY_TOP_LEVEL_HELP,
        description=POLICY_PARSER_DESCRIPTION,
    )
    configure_policy_parser(policy)

    server = top.add_parser(
        'server',
        help=SERVER_TOP_LEVEL_HELP,
        description=SERVER_PARSER_DESCRIPTION,
    )
    configure_server_parser(server)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, '_handler', None)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == '__main__':
    raise SystemExit(main())
