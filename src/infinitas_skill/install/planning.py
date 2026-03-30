"""Install planning CLI helpers built around the legacy dependency planner."""

import argparse
import json
import sys

from infinitas_skill.install.service import (
    DependencyError,
    error_to_payload,
    plan_from_skill_dir,
    plan_to_text,
)

INSTALL_MODES = ('install', 'sync')


def _display_identity(item):
    if not isinstance(item, dict):
        return None
    return item.get('qualified_name') or item.get('name')


def emit_resolve_install_plan_error(exc, *, stderr=None):
    stderr = stderr or sys.stderr
    payload = error_to_payload(exc)

    print(f"FAIL: {payload.pop('error')}", file=stderr)
    reason = payload.pop('reason', None)
    if reason:
        print(f'  reason: {reason}', file=stderr)
    selected = payload.pop('selected', None)
    if selected:
        print(
            f"  selected: {_display_identity(selected)}@{selected.get('version')} "
            f"from {selected.get('registry')} ({selected.get('stage')})",
            file=stderr,
        )
    installed = payload.pop('installed', None)
    if installed:
        print(
            f"  installed: {_display_identity(installed)}@{installed.get('version')} "
            f"locked={installed.get('locked_version')} from {installed.get('registry')}",
            file=stderr,
        )
    conflict = payload.pop('conflict', None)
    if conflict:
        registry = f" [{conflict.get('registry')}]" if conflict.get('registry') else ''
        print(f"  conflict: {conflict.get('name')}{registry} {conflict.get('version')}", file=stderr)
    constraints = payload.pop('constraints', None)
    if constraints:
        print('  constraints:', file=stderr)
        for entry in constraints:
            registry = f" [{entry.get('registry')}]" if entry.get('registry') else ''
            source = f" <= {entry.get('source_name')}@{entry.get('source_version')}" if entry.get('source_name') else ''
            incubating = ' +incubating' if entry.get('allow_incubating') else ''
            print(
                f"    - {_display_identity(entry)}{registry} {entry.get('version')}{incubating}{source}",
                file=stderr,
            )
    available = payload.pop('available', None)
    if available:
        print('  available candidates:', file=stderr)
        for item in available:
            print(
                f"    - {item.get('name')}@{item.get('version')} from {item.get('registry')} ({item.get('stage')})",
                file=stderr,
            )
    rejected = payload.pop('rejected_candidates', None)
    if rejected:
        print('  rejected candidates:', file=stderr)
        for item in rejected:
            candidate = item.get('candidate') or {}
            print(
                f"    - {candidate.get('name')}@{candidate.get('version')} "
                f"from {candidate.get('registry')} ({candidate.get('stage')}): {item.get('reason')}",
                file=stderr,
            )
    missing = payload.pop('missing_registry_roots', None)
    if missing:
        unresolved = {key: value for key, value in missing.items() if value}
        if unresolved:
            print('  missing registry roots:', file=stderr)
            for key, value in sorted(unresolved.items()):
                print(f'    - {key}: {value}', file=stderr)


def emit_check_install_target_error(exc, *, stderr=None):
    stderr = stderr or sys.stderr
    payload = error_to_payload(exc)

    print(f"FAIL: {payload.pop('error')}", file=stderr)
    reason = payload.pop('reason', None)
    if reason:
        print(f'  reason: {reason}', file=stderr)
    constraints = payload.pop('constraints', None)
    if constraints:
        print('  constraints:', file=stderr)
        for entry in constraints:
            registry = f" [{entry.get('registry')}]" if entry.get('registry') else ''
            source = f" <= {entry.get('source_name')}@{entry.get('source_version')}" if entry.get('source_name') else ''
            incubating = ' +incubating' if entry.get('allow_incubating') else ''
            print(
                f"    - {_display_identity(entry)}{registry} {entry.get('version')}{incubating}{source}",
                file=stderr,
            )
    selected = payload.pop('selected', None)
    if selected:
        print(
            f"  selected: {_display_identity(selected)}@{selected.get('version')} "
            f"from {selected.get('registry')} ({selected.get('stage')})",
            file=stderr,
        )
    installed = payload.pop('installed', None)
    if installed:
        print(
            f"  installed: {_display_identity(installed)}@{installed.get('version')} "
            f"locked={installed.get('locked_version')} from {installed.get('registry')}",
            file=stderr,
        )
    conflict = payload.pop('conflict', None)
    if conflict:
        registry = f" [{conflict.get('registry')}]" if conflict.get('registry') else ''
        print(f"  conflict: {conflict.get('name')}{registry} {conflict.get('version')}", file=stderr)
    available = payload.pop('available', None)
    if available:
        print('  available candidates:', file=stderr)
        for item in available:
            print(
                f"    - {_display_identity(item)}@{item.get('version')} "
                f"from {item.get('registry')} ({item.get('stage')})",
                file=stderr,
            )


def _load_source_info(source_json: str | None):
    return json.loads(source_json) if source_json else None


def configure_resolve_install_plan_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('--skill-dir', required=True, help='Skill directory to resolve from')
    parser.add_argument('--target-dir', help='Existing install target directory to plan against')
    parser.add_argument('--source-registry', help='Registry hint for the root skill source')
    parser.add_argument('--source-json', help='Resolved source metadata JSON for the root skill')
    parser.add_argument('--mode', choices=INSTALL_MODES, default='install', help='Whether to plan an install or sync flow')
    parser.add_argument('--json', action='store_true', help='Print machine-readable plan output')
    return parser


def build_resolve_install_plan_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description='Resolve an install or sync dependency plan')
    return configure_resolve_install_plan_parser(parser)


def parse_resolve_install_plan_args(argv: list[str] | None = None, *, prog: str | None = None) -> argparse.Namespace:
    return build_resolve_install_plan_parser(prog=prog).parse_args(argv)


def run_resolve_install_plan(
    *,
    skill_dir: str,
    target_dir: str | None = None,
    source_registry: str | None = None,
    source_json: str | None = None,
    mode: str = 'install',
    as_json: bool = False,
) -> int:
    source_info = _load_source_info(source_json)
    try:
        plan = plan_from_skill_dir(
            skill_dir,
            target_dir=target_dir,
            source_registry=source_registry,
            source_info=source_info,
            mode=mode,
        )
    except DependencyError as exc:
        emit_resolve_install_plan_error(exc)
        return 1

    if as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(plan_to_text(plan))
    return 0


def resolve_install_plan_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    args = parse_resolve_install_plan_args(argv, prog=prog)
    return run_resolve_install_plan(
        skill_dir=args.skill_dir,
        target_dir=args.target_dir,
        source_registry=args.source_registry,
        source_json=args.source_json,
        mode=args.mode,
        as_json=args.json,
    )


def configure_check_install_target_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument('skill_dir', help='Skill directory to validate')
    parser.add_argument('target_dir', help='Install target directory to validate against')
    parser.add_argument('--source-registry', help='Registry hint for the root skill source')
    parser.add_argument('--source-json', help='Resolved source metadata JSON for the root skill')
    parser.add_argument('--mode', choices=INSTALL_MODES, default='install', help='Whether to check an install or sync flow')
    parser.add_argument('--json', action='store_true', help='Print machine-readable plan output')
    return parser


def build_check_install_target_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description='Check whether an install target is dependency-safe')
    return configure_check_install_target_parser(parser)


def parse_check_install_target_args(argv: list[str] | None = None, *, prog: str | None = None) -> argparse.Namespace:
    return build_check_install_target_parser(prog=prog).parse_args(argv)


def run_check_install_target(
    *,
    skill_dir: str,
    target_dir: str,
    source_registry: str | None = None,
    source_json: str | None = None,
    mode: str = 'install',
    as_json: bool = False,
) -> int:
    source_info = _load_source_info(source_json)
    try:
        plan = plan_from_skill_dir(
            skill_dir,
            target_dir=target_dir,
            source_registry=source_registry,
            source_info=source_info,
            mode=mode,
        )
    except DependencyError as exc:
        emit_check_install_target_error(exc)
        return 1

    if as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        root = plan.get('root', {})
        name = root.get('qualified_name') or root.get('name')
        print(f'OK: install target check passed for {name}')
    return 0


def check_install_target_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    args = parse_check_install_target_args(argv, prog=prog)
    return run_check_install_target(
        skill_dir=args.skill_dir,
        target_dir=args.target_dir,
        source_registry=args.source_registry,
        source_json=args.source_json,
        mode=args.mode,
        as_json=args.json,
    )


__all__ = [
    'DependencyError',
    'INSTALL_MODES',
    'build_check_install_target_parser',
    'build_resolve_install_plan_parser',
    'check_install_target_main',
    'configure_check_install_target_parser',
    'configure_resolve_install_plan_parser',
    'emit_check_install_target_error',
    'emit_resolve_install_plan_error',
    'error_to_payload',
    'parse_check_install_target_args',
    'parse_resolve_install_plan_args',
    'plan_from_skill_dir',
    'plan_to_text',
    'resolve_install_plan_main',
    'run_check_install_target',
    'run_resolve_install_plan',
]
