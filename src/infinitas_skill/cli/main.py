import argparse

from infinitas_skill.release.state import RELEASE_STATE_MODES, run_release_check_state


def _build_release_check_state_parser(subparsers):
    parser = subparsers.add_parser('check-state', help='Check stable release invariants for a skill')
    parser.add_argument('skill', help='Skill name or path')
    parser.add_argument(
        '--mode',
        choices=RELEASE_STATE_MODES,
        default='stable-release',
        help='Which release invariant set to enforce',
    )
    parser.add_argument('--json', action='store_true', help='Print machine-readable state')
    parser.add_argument('--debug-policy', action='store_true', help='Print a human-readable policy trace')
    parser.set_defaults(
        _handler=lambda args: run_release_check_state(
            args.skill,
            mode=args.mode,
            as_json=args.json,
            debug_policy=args.debug_policy,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='infinitas', description='infinitas project CLI')
    top = parser.add_subparsers(dest='command')

    release = top.add_parser('release', help='Release tools')
    release_sub = release.add_subparsers(dest='release_command')
    _build_release_check_state_parser(release_sub)

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
