#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path

from dependency_lib import DependencyError, normalize_meta_dependencies
from registry_source_lib import load_registry_config

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?$')
ALLOWED_STATUS = {'incubating', 'active', 'archived'}
ALLOWED_REVIEW = {'draft', 'under-review', 'approved', 'rejected'}
ALLOWED_RISK = {'low', 'medium', 'high'}
KNOWN_REGISTRIES = {reg.get('name') for reg in load_registry_config(ROOT).get('registries', []) if reg.get('name')}


def fail(msg: str):
    print(f'FAIL: {msg}', file=sys.stderr)


def validate_meta(skill_dir: Path) -> int:
    errors = 0
    meta_path = skill_dir / '_meta.json'
    skill_md = skill_dir / 'SKILL.md'
    if not meta_path.exists() or not skill_md.exists():
        fail(f'{skill_dir}: missing SKILL.md or _meta.json')
        return 1
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    except Exception as e:
        fail(f'{skill_dir}: invalid JSON in _meta.json: {e}')
        return 1

    def req(key):
        nonlocal errors
        if key not in meta:
            fail(f'{skill_dir}: missing required field {key}')
            errors += 1

    for key in ['name', 'version', 'status', 'summary', 'owner', 'review_state', 'risk_level', 'distribution']:
        req(key)

    name = meta.get('name')
    if not isinstance(name, str) or not NAME_RE.match(name):
        fail(f'{skill_dir}: invalid name {name!r}')
        errors += 1
    elif skill_dir.parent.name != 'archived' and name != skill_dir.name:
        fail(f'{skill_dir}: meta name {name!r} does not match folder name {skill_dir.name!r}')
        errors += 1

    version = meta.get('version')
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        fail(f'{skill_dir}: invalid version {version!r}')
        errors += 1

    status = meta.get('status')
    if status not in ALLOWED_STATUS:
        fail(f'{skill_dir}: invalid status {status!r}')
        errors += 1
    else:
        parent = skill_dir.parent.name
        if parent in ALLOWED_STATUS and status != parent:
            fail(f'{skill_dir}: status {status!r} does not match parent directory {parent!r}')
            errors += 1

    if not isinstance(meta.get('summary'), str) or not meta.get('summary', '').strip():
        fail(f'{skill_dir}: summary must be a non-empty string')
        errors += 1
    if not isinstance(meta.get('owner'), str) or not meta.get('owner', '').strip():
        fail(f'{skill_dir}: owner must be a non-empty string')
        errors += 1

    review = meta.get('review_state')
    if review not in ALLOWED_REVIEW:
        fail(f'{skill_dir}: invalid review_state {review!r}')
        errors += 1

    risk = meta.get('risk_level')
    if risk not in ALLOWED_RISK:
        fail(f'{skill_dir}: invalid risk_level {risk!r}')
        errors += 1

    for list_key in ['maintainers', 'tags', 'agent_compatible']:
        if list_key in meta and not (isinstance(meta[list_key], list) and all(isinstance(x, str) for x in meta[list_key])):
            fail(f'{skill_dir}: {list_key} must be an array of strings')
            errors += 1

    try:
        normalized_dependencies = normalize_meta_dependencies(meta)
    except DependencyError as exc:
        fail(f'{skill_dir}: {exc.message}')
        errors += 1
        normalized_dependencies = {'depends_on': [], 'conflicts_with': []}

    for field, entries in normalized_dependencies.items():
        for entry in entries:
            registry = entry.get('registry')
            if registry and registry not in KNOWN_REGISTRIES:
                fail(f'{skill_dir}: {field} entry for {entry.get("name")} references unknown registry {registry!r}')
                errors += 1

    for nullable_key in ['derived_from', 'replaces']:
        if nullable_key in meta and meta[nullable_key] is not None and not isinstance(meta[nullable_key], str):
            fail(f'{skill_dir}: {nullable_key} must be null or string')
            errors += 1

    for string_key in ['snapshot_of', 'snapshot_created_at', 'snapshot_label']:
        if string_key in meta and not isinstance(meta[string_key], str):
            fail(f'{skill_dir}: {string_key} must be a string when present')
            errors += 1

    requires = meta.get('requires', {})
    if requires and not isinstance(requires, dict):
        fail(f'{skill_dir}: requires must be an object')
        errors += 1
    elif isinstance(requires, dict):
        for key in ['tools', 'bins', 'env']:
            if key in requires and not (isinstance(requires[key], list) and all(isinstance(x, str) for x in requires[key])):
                fail(f'{skill_dir}: requires.{key} must be an array of strings')
                errors += 1

    entrypoints = meta.get('entrypoints', {})
    if entrypoints and not isinstance(entrypoints, dict):
        fail(f'{skill_dir}: entrypoints must be an object')
        errors += 1
    else:
        skill_md_rel = entrypoints.get('skill_md', 'SKILL.md') if isinstance(entrypoints, dict) else 'SKILL.md'
        if skill_md_rel != 'SKILL.md':
            fail(f'{skill_dir}: entrypoints.skill_md should be SKILL.md for MVP')
            errors += 1

    tests = meta.get('tests', {})
    if tests and not isinstance(tests, dict):
        fail(f'{skill_dir}: tests must be an object')
        errors += 1
        smoke_rel = 'tests/smoke.md'
    else:
        smoke_rel = tests.get('smoke', 'tests/smoke.md') if isinstance(tests, dict) else 'tests/smoke.md'
    if not (skill_dir / smoke_rel).is_file():
        fail(f'{skill_dir}: missing smoke test file {smoke_rel!r}')
        errors += 1

    distribution = meta.get('distribution')
    if not isinstance(distribution, dict):
        fail(f'{skill_dir}: distribution must be an object')
        errors += 1
    else:
        if not isinstance(distribution.get('installable'), bool):
            fail(f'{skill_dir}: distribution.installable must be boolean')
            errors += 1
        if not isinstance(distribution.get('channel'), str) or not distribution.get('channel', '').strip():
            fail(f'{skill_dir}: distribution.channel must be non-empty string')
            errors += 1

    return errors


def collect_dirs(args):
    if args:
        dirs = []
        for arg in args:
            p = (ROOT / arg).resolve() if not os.path.isabs(arg) else Path(arg)
            if p.is_dir() and (p / '_meta.json').exists():
                dirs.append(p)
            elif p.is_dir():
                for child in sorted(x for x in p.iterdir() if x.is_dir() and (x / '_meta.json').exists()):
                    dirs.append(child)
            else:
                fail(f'path does not exist or is not a directory: {arg}')
                return []
        return dirs

    dirs = []
    for base in [ROOT / 'skills' / 'incubating', ROOT / 'skills' / 'active', ROOT / 'skills' / 'archived', ROOT / 'templates']:
        if not base.exists():
            continue
        for child in sorted(x for x in base.iterdir() if x.is_dir() and (x / '_meta.json').exists()):
            dirs.append(child)
    return dirs


def main():
    dirs = collect_dirs(sys.argv[1:])
    if not dirs:
        print('No skill directories found.' if len(sys.argv) == 1 else 'Nothing to validate.', file=sys.stderr)
        return 1
    errors = 0
    for d in dirs:
        errors += validate_meta(d)
    if errors:
        print(f'Validation failed with {errors} error(s).', file=sys.stderr)
        return 1
    print(f'OK: validated {len(dirs)} skill directories')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
