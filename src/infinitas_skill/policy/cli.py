"""Parser and dispatch glue for policy commands."""

from __future__ import annotations

import argparse

from infinitas_skill.policy.service import run_check_policy_packs, run_check_promotion

POLICY_TOP_LEVEL_HELP = 'Policy validation and promotion tools'
POLICY_PARSER_DESCRIPTION = 'Policy validation and promotion CLI'


def configure_check_policy_packs_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    return parser


def configure_check_promotion_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('targets', nargs='*', help='Skill directory path(s) to check')
    parser.add_argument('--as-active', action='store_true', help='Evaluate targets as active-stage skills')
    parser.add_argument('--json', action='store_true', help='Print machine-readable output')
    parser.add_argument('--debug-policy', action='store_true', help='Print a human-readable policy trace')
    return parser


def build_check_policy_packs_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Validate policy-pack selector and active pack files', prog=prog)
    return configure_check_policy_packs_parser(parser)


def build_check_promotion_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Check active promotion policy for one or more skills', prog=prog)
    return configure_check_promotion_parser(parser)


def configure_policy_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    subparsers = parser.add_subparsers(dest='policy_command', metavar='{check-packs,check-promotion}')

    check_packs = subparsers.add_parser('check-packs', parents=[build_check_policy_packs_parser()], add_help=False)
    check_packs.description = 'Validate policy-pack selector and active pack files'
    check_packs.help = 'Validate policy-pack selector and active pack files'
    check_packs.set_defaults(_handler=lambda _args: run_check_policy_packs())

    check_promotion = subparsers.add_parser('check-promotion', parents=[build_check_promotion_parser()], add_help=False)
    check_promotion.description = 'Check active promotion policy for one or more skills'
    check_promotion.help = 'Check active promotion policy for one or more skills'
    check_promotion.set_defaults(
        _handler=lambda args: run_check_promotion(
            targets=args.targets,
            as_active=args.as_active,
            as_json=args.json,
            debug_policy=args.debug_policy,
        )
    )
    return parser


def build_policy_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=POLICY_PARSER_DESCRIPTION, prog=prog)
    return configure_policy_parser(parser)


def policy_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    parser = build_policy_parser(prog=prog)
    args = parser.parse_args(argv)
    handler = getattr(args, '_handler', None)
    if handler is None:
        parser.print_help()
        return 0
    return handler(args)


__all__ = [
    'POLICY_PARSER_DESCRIPTION',
    'POLICY_TOP_LEVEL_HELP',
    'build_check_policy_packs_parser',
    'build_check_promotion_parser',
    'build_policy_parser',
    'configure_check_policy_packs_parser',
    'configure_check_promotion_parser',
    'configure_policy_parser',
    'policy_main',
    'run_check_policy_packs',
    'run_check_promotion',
]
