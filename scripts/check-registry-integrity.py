#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from dependency_lib import DependencyError, constraint_display, normalize_meta_dependencies, plan_from_skill_dir
from registry_source_lib import load_registry_config

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = load_registry_config(ROOT).get('default_registry') or 'self'


def load_skills():
    items = []
    for stage in ['incubating', 'active', 'archived', 'templates']:
        base = ROOT / 'templates' if stage == 'templates' else ROOT / 'skills' / stage
        if not base.exists():
            continue
        for skill_dir in sorted(path for path in base.iterdir() if path.is_dir() and (path / '_meta.json').exists()):
            meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
            items.append((stage, skill_dir, meta))
    return items


def matches_entry(entry, name, version):
    if entry.get('name') != name:
        return False
    expected = entry.get('version') or '*'
    if expected == '*':
        return True
    return expected == f'={version}' or expected == version


def print_dependency_error(prefix, exc):
    print(f'FAIL: {prefix}: {exc.message}', file=sys.stderr)
    details = exc.details or {}
    reason = details.get('reason')
    if reason:
        print(f'  reason: {reason}', file=sys.stderr)
    constraints = details.get('constraints') or []
    if constraints:
        print('  constraints:', file=sys.stderr)
        for entry in constraints:
            source = f" <= {entry.get('source_name')}@{entry.get('source_version')}" if entry.get('source_name') else ''
            print(f"    - {constraint_display(entry)}{source}", file=sys.stderr)
    available = details.get('available') or []
    if available:
        print('  available:', file=sys.stderr)
        for item in available:
            print(
                f"    - {item.get('name')}@{item.get('version')} from {item.get('registry')} ({item.get('stage')})",
                file=sys.stderr,
            )


def main():
    items = load_skills()
    errors = 0
    warnings = 0
    normalized = {}
    active_installable = []

    for stage, skill_dir, meta in items:
        try:
            entry = normalize_meta_dependencies(meta)
        except DependencyError as exc:
            print_dependency_error(str(skill_dir), exc)
            errors += 1
            continue
        normalized[str(skill_dir)] = entry
        if stage == 'active' and meta.get('distribution', {}).get('installable', True):
            active_installable.append((skill_dir, meta, entry))

    active_names = {meta.get('name'): (skill_dir, meta, entry) for skill_dir, meta, entry in active_installable}
    for skill_dir, meta, entry in active_installable:
        for conflict in entry.get('conflicts_with', []):
            other = active_names.get(conflict.get('name'))
            if not other or other[1].get('name') == meta.get('name'):
                continue
            if matches_entry(conflict, other[1].get('name'), other[1].get('version')):
                warnings += 1
                print(
                    f'WARN: {meta.get("name")} conflicts with active skill {other[1].get("name")} ({other[0]})',
                    file=sys.stderr,
                )

    for skill_dir, meta, _entry in active_installable:
        try:
            plan_from_skill_dir(skill_dir, source_registry=DEFAULT_REGISTRY, mode='install')
        except DependencyError as exc:
            print_dependency_error(str(skill_dir), exc)
            errors += 1

    if errors:
        print(f'Integrity check failed with {errors} error(s) and {warnings} warning(s).', file=sys.stderr)
        return 1
    print(f'OK: registry integrity checked across {len(items)} skill directories ({warnings} warning(s))')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
