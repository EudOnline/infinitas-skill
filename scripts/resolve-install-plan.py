#!/usr/bin/env python3
import argparse
import json
import sys

from dependency_lib import DependencyError, error_to_payload, plan_from_skill_dir, plan_to_text


def print_error(exc):
    payload = error_to_payload(exc)
    print(f"FAIL: {payload.pop('error')}", file=sys.stderr)
    reason = payload.pop('reason', None)
    if reason:
        print(f'  reason: {reason}', file=sys.stderr)
    selected = payload.pop('selected', None)
    if selected:
        print(
            f"  selected: {selected.get('name')}@{selected.get('version')} from {selected.get('registry')} ({selected.get('stage')})",
            file=sys.stderr,
        )
    installed = payload.pop('installed', None)
    if installed:
        print(
            f"  installed: {installed.get('name')}@{installed.get('version')} locked={installed.get('locked_version')} from {installed.get('registry')}",
            file=sys.stderr,
        )
    conflict = payload.pop('conflict', None)
    if conflict:
        registry = f" [{conflict.get('registry')}]" if conflict.get('registry') else ''
        print(f"  conflict: {conflict.get('name')}{registry} {conflict.get('version')}", file=sys.stderr)
    constraints = payload.pop('constraints', None)
    if constraints:
        print('  constraints:', file=sys.stderr)
        for entry in constraints:
            registry = f" [{entry.get('registry')}]" if entry.get('registry') else ''
            source = f" <= {entry.get('source_name')}@{entry.get('source_version')}" if entry.get('source_name') else ''
            incubating = ' +incubating' if entry.get('allow_incubating') else ''
            print(f"    - {entry.get('name')}{registry} {entry.get('version')}{incubating}{source}", file=sys.stderr)
    available = payload.pop('available', None)
    if available:
        print('  available candidates:', file=sys.stderr)
        for item in available:
            print(
                f"    - {item.get('name')}@{item.get('version')} from {item.get('registry')} ({item.get('stage')})",
                file=sys.stderr,
            )
    rejected = payload.pop('rejected_candidates', None)
    if rejected:
        print('  rejected candidates:', file=sys.stderr)
        for item in rejected:
            candidate = item.get('candidate') or {}
            print(
                f"    - {candidate.get('name')}@{candidate.get('version')} from {candidate.get('registry')} ({candidate.get('stage')}): {item.get('reason')}",
                file=sys.stderr,
            )
    missing = payload.pop('missing_registry_roots', None)
    if missing:
        unresolved = {key: value for key, value in missing.items() if value}
        if unresolved:
            print('  missing registry roots:', file=sys.stderr)
            for key, value in sorted(unresolved.items()):
                print(f'    - {key}: {value}', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--target-dir')
    parser.add_argument('--source-registry')
    parser.add_argument('--source-json')
    parser.add_argument('--mode', choices=['install', 'sync'], default='install')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    source_info = json.loads(args.source_json) if args.source_json else None
    try:
        plan = plan_from_skill_dir(
            args.skill_dir,
            target_dir=args.target_dir,
            source_registry=args.source_registry,
            source_info=source_info,
            mode=args.mode,
        )
    except DependencyError as exc:
        print_error(exc)
        return 1

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        print(plan_to_text(plan))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
