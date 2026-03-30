"""Maintained CLI entrypoints for release state checks."""

import argparse
import json
import sys
from pathlib import Path

from infinitas_skill.policy.trace import render_policy_trace
from infinitas_skill.release.formatting import format_release_state
from infinitas_skill.release.service import (
    ROOT,
    RELEASE_STATE_MODES,
    ReleaseError,
    collect_platform_compatibility_state,
    collect_release_state,
    collect_reproducibility_state,
    collect_transparency_log_state,
    expected_skill_tag,
    git,
    load_json,
    load_signing_config,
    resolve_releaser_identity,
    resolve_skill,
    signer_entries,
    signing_key_path,
)


def configure_release_check_state_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('skill', help='Skill name or path')
    parser.add_argument(
        '--mode',
        choices=RELEASE_STATE_MODES,
        default='stable-release',
        help='Which release invariant set to enforce',
    )
    parser.add_argument('--json', action='store_true', help='Print machine-readable state')
    parser.add_argument('--debug-policy', action='store_true', help='Print a human-readable policy trace')
    return parser


def build_release_check_state_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description='Check stable release invariants for a skill',
    )
    return configure_release_check_state_parser(parser)


def parse_release_check_state_args(argv: list[str] | None = None, *, prog: str | None = None) -> argparse.Namespace:
    return build_release_check_state_parser(prog=prog).parse_args(argv)


def run_release_check_state(
    skill: str,
    *,
    mode: str = 'stable-release',
    as_json: bool = False,
    debug_policy: bool = False,
    root: str | Path | None = None,
) -> int:
    try:
        skill_dir = resolve_skill(Path(root).resolve() if root else ROOT, skill)
        state = collect_release_state(skill_dir, mode=mode, root=root)
    except ReleaseError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print(format_release_state(state))
        if debug_policy:
            print()
            print(render_policy_trace(state.get('policy_trace') or {}))

    return 0 if state['release_ready'] else 1


def release_check_state_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    args = parse_release_check_state_args(argv, prog=prog)
    return run_release_check_state(
        args.skill,
        mode=args.mode,
        as_json=args.json,
        debug_policy=args.debug_policy,
    )


__all__ = [
    'ROOT',
    'RELEASE_STATE_MODES',
    'ReleaseError',
    'git',
    'load_json',
    'resolve_skill',
    'load_signing_config',
    'resolve_releaser_identity',
    'signer_entries',
    'signing_key_path',
    'expected_skill_tag',
    'collect_reproducibility_state',
    'collect_transparency_log_state',
    'collect_platform_compatibility_state',
    'collect_release_state',
    'configure_release_check_state_parser',
    'format_release_state',
    'build_release_check_state_parser',
    'parse_release_check_state_args',
    'run_release_check_state',
    'release_check_state_main',
]
