#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

from dependency_lib import DependencyError, normalize_meta_dependencies
from ai_index_lib import validate_ai_index_payload
from discovery_index_lib import validate_discovery_index_payload
from compatibility_evidence_lib import compatibility_evidence_root, validate_compatibility_evidence_payload
from policy_pack_lib import PolicyPackError, load_policy_domain_resolution
from policy_trace_lib import build_policy_trace, render_policy_trace
from registry_source_lib import load_registry_config
from skill_identity_lib import NamespacePolicyError, load_namespace_policy, namespace_policy_report, validate_identity_metadata
from schema_version_lib import validate_schema_version
from canonical_skill_lib import CanonicalSkillError, is_canonical_skill_dir, validate_canonical_payload

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?$')
FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n?', re.DOTALL)
ALLOWED_STATUS = {'incubating', 'active', 'archived'}
ALLOWED_REVIEW = {'draft', 'under-review', 'approved', 'rejected'}
ALLOWED_RISK = {'low', 'medium', 'high'}
KNOWN_REGISTRIES = {reg.get('name') for reg in load_registry_config(ROOT).get('registries', []) if reg.get('name')}
ERROR_COLLECTOR = None


def fail(msg: str):
    print(f'FAIL: {msg}', file=sys.stderr)
    if isinstance(ERROR_COLLECTOR, list):
        ERROR_COLLECTOR.append(msg)


def _repo_relative_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def _is_registry_skill_dir(skill_dir: Path) -> bool:
    try:
        skill_dir.resolve().relative_to((ROOT / 'skills').resolve())
        return True
    except ValueError:
        return False


def _parse_frontmatter(skill_md_path: Path):
    content = skill_md_path.read_text(encoding='utf-8')
    match = FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError(f'missing YAML frontmatter in {skill_md_path}')

    fields = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or ':' not in line:
            continue
        key, value = line.split(':', 1)
        cleaned = value.strip()
        if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
            cleaned = cleaned[1:-1]
        fields[key.strip()] = cleaned

    name = fields.get('name')
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f'missing frontmatter name in {skill_md_path}')
    description = fields.get('description')
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f'missing frontmatter description in {skill_md_path}')
    return fields


def validate_canonical_skill(skill_dir: Path) -> int:
    errors = 0
    payload_path = skill_dir / 'skill.json'
    instructions_path = skill_dir / 'instructions.md'
    if not payload_path.exists():
        fail(f'{skill_dir}: missing skill.json')
        return 1
    try:
        payload = json.loads(payload_path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'{skill_dir}: invalid JSON in skill.json: {exc}')
        return 1
    for error in validate_canonical_payload(payload):
        fail(f'{skill_dir}: {error}')
        errors += 1
    instructions_rel = payload.get('instructions_body', 'instructions.md') if isinstance(payload, dict) else 'instructions.md'
    if not (skill_dir / instructions_rel).is_file():
        fail(f'{skill_dir}: missing canonical instructions body {instructions_rel!r}')
        errors += 1
    platforms_dir = skill_dir / 'platforms'
    if platforms_dir.exists() and not platforms_dir.is_dir():
        fail(f'{skill_dir}: platforms must be a directory when present')
        errors += 1
    return errors


def validate_meta(skill_dir: Path, namespace_policy=None) -> int:
    if is_canonical_skill_dir(skill_dir):
        return validate_canonical_skill(skill_dir)
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

    _schema_version, schema_errors = validate_schema_version(meta)
    for error in schema_errors:
        fail(f'{skill_dir}: {error}')
        errors += 1

    def req(key):
        nonlocal errors
        if key not in meta:
            fail(f'{skill_dir}: missing required field {key}')
            errors += 1

    for key in ['name', 'version', 'status', 'summary', 'owner', 'review_state', 'risk_level', 'distribution']:
        req(key)

    frontmatter = {}
    try:
        frontmatter = _parse_frontmatter(skill_md)
    except ValueError as exc:
        fail(f'{skill_dir}: {exc}')
        errors += 1

    name = meta.get('name')
    if not isinstance(name, str) or not NAME_RE.match(name):
        fail(f'{skill_dir}: invalid name {name!r}')
        errors += 1
    elif skill_dir.parent.name != 'archived' and name != skill_dir.name:
        fail(f'{skill_dir}: meta name {name!r} does not match folder name {skill_dir.name!r}')
        errors += 1

    frontmatter_name = frontmatter.get('name') if isinstance(frontmatter, dict) else None
    if isinstance(frontmatter_name, str) and frontmatter_name != name:
        fail(f'{skill_dir}: frontmatter name {frontmatter_name!r} does not match _meta.json name {name!r}')
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

    _identity, identity_errors = validate_identity_metadata(meta)
    for error in identity_errors:
        fail(f'{skill_dir}: {error}')
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

    if distribution and distribution.get('installable') is True:
        description = frontmatter.get('description') if isinstance(frontmatter, dict) else None
        if not isinstance(description, str) or not description.strip():
            fail(f'{skill_dir}: missing frontmatter description for installable skill')
            errors += 1

    if _is_registry_skill_dir(skill_dir):
        report = namespace_policy_report(skill_dir, root=ROOT, policy=namespace_policy)
        for message in report.get('errors', []):
            fail(message)
            errors += 1

    return errors


def validate_ai_index(root: Path) -> int:
    path = root / 'catalog' / 'ai-index.json'
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'{path}: invalid JSON: {exc}')
        return 1
    errors = validate_ai_index_payload(payload)
    for error in errors:
        fail(f'{path}: {error}')
    return len(errors)


def validate_discovery_index(root: Path) -> int:
    path = root / 'catalog' / 'discovery-index.json'
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'{path}: invalid JSON: {exc}')
        return 1
    errors = validate_discovery_index_payload(payload)
    for error in errors:
        fail(f'{path}: {error}')
    return len(errors)


def validate_compatibility_evidence(root: Path) -> int:
    evidence_root = compatibility_evidence_root(root)
    if not evidence_root.exists():
        return 0

    errors = 0
    for path in sorted(evidence_root.rglob('*.json')):
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except Exception as exc:
            fail(f'{path}: invalid JSON: {exc}')
            errors += 1
            continue
        rel_path = path.relative_to(evidence_root)
        payload_errors = validate_compatibility_evidence_payload(payload, path=rel_path)
        for error in payload_errors:
            fail(f'{path}: {error}')
            errors += 1
    return errors


def collect_dirs(args):
    if args:
        dirs = []
        for arg in args:
            p = (ROOT / arg).resolve() if not os.path.isabs(arg) else Path(arg).resolve()
            if p.is_dir() and ((p / '_meta.json').exists() or is_canonical_skill_dir(p)):
                dirs.append(p)
            elif p.is_dir():
                for child in sorted(
                    x.resolve() for x in p.iterdir() if x.is_dir() and ((x / '_meta.json').exists() or is_canonical_skill_dir(x))
                ):
                    dirs.append(child)
            else:
                fail(f'path does not exist or is not a directory: {arg}')
                return []
        return dirs

    dirs = []
    for base in [ROOT / 'skills' / 'incubating', ROOT / 'skills' / 'active', ROOT / 'skills' / 'archived', ROOT / 'templates', ROOT / 'skills-src']:
        if not base.exists():
            continue
        for child in sorted(
            x.resolve() for x in base.iterdir() if x.is_dir() and ((x / '_meta.json').exists() or is_canonical_skill_dir(x))
        ):
            dirs.append(child)
    return dirs


def build_namespace_policy_trace(skill_dir: Path, namespace_policy, effective_sources):
    report = namespace_policy_report(skill_dir, root=ROOT, policy=namespace_policy)
    identity = report.get('identity') or {}
    competing_claims = report.get('competing_claims') or []
    reasons = list(report.get('warnings') or [])
    if report.get('transfer_required'):
        reasons.append('namespace transfer review was required because another claim for the same skill name exists')
    if competing_claims:
        reasons.append(f'competing_claim_count={len(competing_claims)}')
    return {
        'skill_path': _repo_relative_path(skill_dir),
        **build_policy_trace(
            domain='namespace_policy',
            decision='allow' if report.get('authorized') else 'deny',
            summary='namespace policy accepted the skill identity claim' if report.get('authorized') else 'namespace policy rejected the skill identity claim',
            effective_sources=effective_sources,
            applied_rules=[
                {'rule': 'publisher claims must exist in namespace policy', 'value': identity.get('publisher') or 'unqualified'},
                {'rule': 'owners and maintainers must be authorized for the publisher', 'value': (identity.get('qualified_name') or identity.get('name'))},
                {'rule': 'conflicting publisher claims require an authorized transfer', 'value': report.get('transfer_required', False)},
            ],
            blocking_rules=[{'rule': message, 'message': message} for message in report.get('errors', [])],
            reasons=reasons,
            next_actions=[
                'review policy/namespace-policy.json and the active policy packs for publisher ownership',
                'resolve unauthorized transfers or competing namespace claims',
            ] if report.get('errors') else ['namespace policy accepted the current identity claim'],
        ),
    }


def parse_args():
    parser = argparse.ArgumentParser(description='Validate registry skill directories and generated catalogs')
    parser.add_argument('paths', nargs='*', help='Skill directories or parent directories to validate')
    parser.add_argument('--json', action='store_true', help='Print machine-readable validation output')
    parser.add_argument('--debug-policy', action='store_true', help='Print human-readable policy traces')
    return parser.parse_args()


def _append_validation_errors(entries, *, scope, path, errors):
    if errors:
        entries.append(
            {
                'scope': scope,
                'path': path,
                'skill_path': path if scope == 'skill' else None,
                'errors': list(errors),
            }
        )


def main():
    global ERROR_COLLECTOR
    args = parse_args()
    dirs = collect_dirs(args.paths)
    if not dirs:
        print('No skill directories found.' if len(args.paths) == 0 else 'Nothing to validate.', file=sys.stderr)
        return 1
    captured_errors = []
    ERROR_COLLECTOR = captured_errors
    namespace_policy_sources = []
    try:
        namespace_resolution = load_policy_domain_resolution(ROOT, 'namespace_policy')
        namespace_policy_sources = namespace_resolution.get('effective_sources', [])
        namespace_policy = load_namespace_policy(ROOT)
    except PolicyPackError as exc:
        for error in exc.errors:
            fail(error)
        return 1
    except NamespacePolicyError as exc:
        for error in exc.errors:
            fail(error)
        return 1
    errors = 0
    policy_traces = []
    validation_errors = []
    try:
        for d in dirs:
            before = len(captured_errors)
            errors += validate_meta(d, namespace_policy=namespace_policy)
            _append_validation_errors(
                validation_errors,
                scope='skill',
                path=_repo_relative_path(d),
                errors=captured_errors[before:],
            )
            if _is_registry_skill_dir(d):
                policy_traces.append(build_namespace_policy_trace(d, namespace_policy, namespace_policy_sources))

        for scope, path, validator in [
            ('catalog', 'catalog/ai-index.json', validate_ai_index),
            ('catalog', 'catalog/discovery-index.json', validate_discovery_index),
            ('compatibility', 'compatibility-evidence', validate_compatibility_evidence),
        ]:
            before = len(captured_errors)
            errors += validator(ROOT)
            _append_validation_errors(
                validation_errors,
                scope=scope,
                path=path,
                errors=captured_errors[before:],
            )
        payload = {
            'ok': errors == 0,
            'validated_skill_count': len(dirs),
            'error_count': errors,
            'validation_errors': validation_errors,
            'policy_traces': policy_traces,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif errors == 0:
            print(f'OK: validated {len(dirs)} skill directories')
            if args.debug_policy:
                for trace in policy_traces:
                    print()
                    print(f"skill_path: {trace.get('skill_path')}")
                    print(render_policy_trace(trace))
        if errors:
            if not args.json:
                print(f'Validation failed with {errors} error(s).', file=sys.stderr)
                if args.debug_policy:
                    for trace in policy_traces:
                        print()
                        print(f"skill_path: {trace.get('skill_path')}", file=sys.stderr)
                        print(render_policy_trace(trace), file=sys.stderr)
            return 1
        return 0
    finally:
        ERROR_COLLECTOR = None


if __name__ == '__main__':
    raise SystemExit(main())
