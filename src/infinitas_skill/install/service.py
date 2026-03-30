"""Install dependency planning service extracted from the legacy scripts/ tree."""

import json
import re
from functools import cmp_to_key
from pathlib import Path

from infinitas_skill.legacy import ROOT, ensure_legacy_scripts_on_path

ensure_legacy_scripts_on_path(ROOT)

from distribution_lib import load_distribution_index
from install_manifest_lib import InstallManifestError, load_install_manifest
from registry_source_lib import load_registry_config, registry_identity, resolve_registry_root
from skill_identity_lib import (
    derive_qualified_name,
    normalize_skill_identity,
    parse_requested_skill,
)

SKILL_NAME_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
LEGACY_REF_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*(?:@\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?)?$')
SEMVER_RE = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$')
COMPARATOR_RE = re.compile(r'^(<=|>=|<|>|=)?(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?)$')


class DependencyError(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


def unique(values):
    seen = set()
    out = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def identity_key_for(payload):
    if not isinstance(payload, dict):
        return None
    return payload.get('qualified_name') or payload.get('name')


def display_identity(payload):
    if not isinstance(payload, dict):
        return None
    return payload.get('qualified_name') or payload.get('name')


def parse_dependency_identity(value, field):
    publisher, name = parse_requested_skill(value)
    if publisher is not None and not SKILL_NAME_RE.match(publisher):
        raise DependencyError(f'{field} entry has invalid publisher {publisher!r}')
    if not isinstance(name, str) or not SKILL_NAME_RE.match(name):
        raise DependencyError(f'{field} entry has invalid name {value!r}')
    qualified_name = derive_qualified_name(name, publisher) if publisher else None
    return {
        'name': name,
        'publisher': publisher,
        'qualified_name': qualified_name,
        'identity_key': qualified_name or name,
    }


def parse_semver(version):
    match = SEMVER_RE.match(version or '')
    if not match:
        raise ValueError(f'invalid semver: {version!r}')
    prerelease = match.group(4)
    prerelease_parts = []
    if prerelease:
        for part in prerelease.split('.'):
            if part.isdigit():
                prerelease_parts.append(int(part))
            else:
                prerelease_parts.append(part)
    return {
        'major': int(match.group(1)),
        'minor': int(match.group(2)),
        'patch': int(match.group(3)),
        'prerelease': tuple(prerelease_parts),
    }


def compare_prerelease(left, right):
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for left_item, right_item in zip(left, right):
        if left_item == right_item:
            continue
        left_num = isinstance(left_item, int)
        right_num = isinstance(right_item, int)
        if left_num and right_num:
            return -1 if left_item < right_item else 1
        if left_num and not right_num:
            return -1
        if not left_num and right_num:
            return 1
        return -1 if left_item < right_item else 1
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


def compare_versions(left, right):
    left_semver = parse_semver(left)
    right_semver = parse_semver(right)
    for key in ['major', 'minor', 'patch']:
        if left_semver[key] == right_semver[key]:
            continue
        return -1 if left_semver[key] < right_semver[key] else 1
    return compare_prerelease(left_semver['prerelease'], right_semver['prerelease'])


def caret_upper_bound(version):
    parsed = parse_semver(version)
    major = parsed['major']
    minor = parsed['minor']
    patch = parsed['patch']
    if major > 0:
        return f'{major + 1}.0.0'
    if minor > 0:
        return f'0.{minor + 1}.0'
    return f'0.0.{patch + 1}'


def tilde_upper_bound(version):
    parsed = parse_semver(version)
    return f"{parsed['major']}.{parsed['minor'] + 1}.0"


def parse_constraint_expression(expression):
    expr = (expression or '*').strip()
    if not expr or expr == '*':
        return []
    comparators = []
    for token in expr.replace(',', ' ').split():
        if token == '*':
            continue
        if token.startswith('^'):
            base = token[1:]
            parse_semver(base)
            comparators.append(('>=', base))
            comparators.append(('<', caret_upper_bound(base)))
            continue
        if token.startswith('~'):
            base = token[1:]
            parse_semver(base)
            comparators.append(('>=', base))
            comparators.append(('<', tilde_upper_bound(base)))
            continue
        match = COMPARATOR_RE.match(token)
        if not match:
            raise ValueError(f'invalid version constraint token: {token!r}')
        op = match.group(1) or '='
        version = match.group(2)
        parse_semver(version)
        comparators.append((op, version))
    return comparators


def canonicalize_constraint(expression):
    expr = (expression or '*').strip()
    if not expr:
        return '*'
    comparators = parse_constraint_expression(expr)
    if not comparators:
        return '*'
    return ' '.join(f'{op}{version}' for op, version in comparators)


def constraint_is_exact(expression):
    comparators = parse_constraint_expression(expression)
    return len(comparators) == 1 and comparators[0][0] == '='


def version_satisfies(version, expression):
    comparators = parse_constraint_expression(expression)
    for op, bound in comparators:
        comparison = compare_versions(version, bound)
        if op == '=' and comparison != 0:
            return False
        if op == '>' and comparison <= 0:
            return False
        if op == '>=' and comparison < 0:
            return False
        if op == '<' and comparison >= 0:
            return False
        if op == '<=' and comparison > 0:
            return False
    return True


def _normalize_entry(entry, field, owner_name=None):
    if isinstance(entry, str):
        name, _, version = entry.partition('@')
        identity = parse_dependency_identity(name, field)
        if version and not SEMVER_RE.match(version):
            raise DependencyError(f'invalid {field} ref {entry!r}')
        normalized = {
            **identity,
            'version': canonicalize_constraint(version or '*'),
            'registry': None,
            'allow_incubating': False,
            'format': 'legacy',
            'raw': entry,
        }
    elif isinstance(entry, dict):
        allowed_keys = {'name', 'version', 'registry', 'allow_incubating'}
        unknown = sorted(set(entry) - allowed_keys)
        if unknown:
            raise DependencyError(f'{field} entry for {entry.get("name") or "<unknown>"} has unsupported keys: {", ".join(unknown)}')
        name = entry.get('name')
        if not isinstance(name, str):
            raise DependencyError(f'{field} entry has invalid name {name!r}')
        identity = parse_dependency_identity(name, field)
        version = entry.get('version', '*')
        if not isinstance(version, str):
            raise DependencyError(f'{field} entry for {identity["identity_key"]} has non-string version constraint')
        registry = entry.get('registry')
        if registry is not None and (not isinstance(registry, str) or not registry.strip()):
            raise DependencyError(f'{field} entry for {identity["identity_key"]} has invalid registry hint {registry!r}')
        allow_incubating = entry.get('allow_incubating', False)
        if not isinstance(allow_incubating, bool):
            raise DependencyError(f'{field} entry for {identity["identity_key"]} has non-boolean allow_incubating')
        normalized = {
            **identity,
            'version': canonicalize_constraint(version),
            'registry': registry.strip() if isinstance(registry, str) and registry.strip() else None,
            'allow_incubating': allow_incubating,
            'format': 'object',
            'raw': entry,
        }
    else:
        raise DependencyError(f'{field} entries must be strings or objects')

    if owner_name and normalized['identity_key'] == owner_name:
        raise DependencyError(f'{field} cannot reference itself ({normalized["identity_key"]})')
    return normalized


def normalize_meta_dependencies(meta, owner_name=None):
    owner_identity = normalize_skill_identity(meta)
    owner = owner_name or identity_key_for(owner_identity) or meta.get('name')
    normalized = {}
    for field in ['depends_on', 'conflicts_with']:
        values = meta.get(field, []) or []
        if not isinstance(values, list):
            raise DependencyError(f'{field} must be an array')
        normalized[field] = [_normalize_entry(entry, field, owner) for entry in values]
    return normalized


def constraint_display(entry):
    registry = f' [{entry["registry"]}]' if entry.get('registry') else ''
    version = entry.get('version') or '*'
    incubating = ' +incubating' if entry.get('allow_incubating') else ''
    return f'{display_identity(entry) or entry["name"]}{registry} {version}{incubating}'.strip()


def load_meta(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def scan_enabled_registry_skills(root):
    cfg = load_registry_config(root)
    enabled = [reg for reg in cfg.get('registries', []) if reg.get('enabled', True)]
    sorted_registries = sorted(
        enabled,
        key=lambda reg: (-int(reg.get('priority', 0)), reg.get('name') or ''),
    )
    registry_identities = {}
    registry_roots = {}
    missing_roots = {}
    candidates = []
    for index, reg in enumerate(sorted_registries):
        reg_name = reg.get('name')
        reg_root = resolve_registry_root(root, reg)
        registry_roots[reg_name] = reg_root
        if reg_root is None or not reg_root.exists():
            missing_roots[reg_name] = str(reg_root) if reg_root else None
            continue
        registry_state = registry_identity(root, reg)
        registry_identities[reg_name] = registry_state
        distribution_index = load_distribution_index(reg_root)
        distribution_by_identity = {
            (entry.get('qualified_name') or entry.get('name'), entry.get('version')): entry for entry in distribution_index
        }
        matched_distribution = set()
        skills_root = reg_root / 'skills'
        for stage in ['active', 'incubating', 'archived']:
            stage_dir = skills_root / stage
            if not stage_dir.exists():
                continue
            for skill_dir in sorted(path for path in stage_dir.iterdir() if path.is_dir() and (path / '_meta.json').exists()):
                meta = load_meta(skill_dir / '_meta.json')
                normalized = normalize_meta_dependencies(meta)
                skill_identity = normalize_skill_identity(meta)
                distribution = distribution_by_identity.get((skill_identity.get('qualified_name') or meta.get('name'), meta.get('version')))
                candidates.append({
                    **registry_state,
                    **skill_identity,
                    'name': meta.get('name'),
                    'publisher': skill_identity.get('publisher'),
                    'qualified_name': skill_identity.get('qualified_name'),
                    'identity_mode': skill_identity.get('identity_mode'),
                    'identity_key': identity_key_for(skill_identity) or meta.get('name'),
                    'version': meta.get('version'),
                    'status': meta.get('status'),
                    'stage': distribution.get('status') if distribution else stage,
                    'path': str((reg_root / distribution.get('manifest_path')).resolve()) if distribution else str(skill_dir),
                    'skill_path': str(skill_dir),
                    'dir_name': skill_dir.name,
                    'relative_path': distribution.get('manifest_path') if distribution else str(skill_dir.relative_to(reg_root)),
                    'installable': bool(meta.get('distribution', {}).get('installable', True)),
                    'snapshot_of': meta.get('snapshot_of'),
                    'snapshot_created_at': distribution.get('generated_at') if distribution else meta.get('snapshot_created_at'),
                    'depends_on': normalized['depends_on'],
                    'conflicts_with': normalized['conflicts_with'],
                    'meta': meta,
                    'source_type': 'distribution-manifest' if distribution else 'working-tree',
                    'distribution_manifest': distribution.get('manifest_path') if distribution else None,
                    'distribution_bundle': distribution.get('bundle_path') if distribution else None,
                    'distribution_bundle_sha256': distribution.get('bundle_sha256') if distribution else None,
                    'distribution_attestation': distribution.get('attestation_path') if distribution else None,
                    'distribution_attestation_signature': distribution.get('attestation_signature_path') if distribution else None,
                    'source_snapshot_kind': distribution.get('source_snapshot_kind') if distribution else None,
                    'source_snapshot_tag': distribution.get('source_snapshot_tag') if distribution else None,
                    'source_snapshot_ref': distribution.get('source_snapshot_ref') if distribution else None,
                    'source_snapshot_commit': distribution.get('source_snapshot_commit') if distribution else None,
                    'registry_commit': distribution.get('source_snapshot_commit') if distribution else registry_state.get('registry_commit'),
                    'registry_tag': distribution.get('source_snapshot_tag') if distribution else registry_state.get('registry_tag'),
                    'registry_ref': distribution.get('source_snapshot_ref') if distribution else registry_state.get('registry_ref'),
                    'registry_priority': int(reg.get('priority', 0)),
                    'registry_order': index,
                    'registry_enabled': reg.get('enabled', True),
                })
                if distribution:
                    matched_distribution.add((skill_identity.get('qualified_name') or meta.get('name'), meta.get('version')))
        for distribution in distribution_index:
            key = (distribution.get('qualified_name') or distribution.get('name'), distribution.get('version'))
            if key in matched_distribution:
                continue
            candidates.append({
                **registry_state,
                'name': distribution.get('name'),
                'publisher': distribution.get('publisher'),
                'qualified_name': distribution.get('qualified_name'),
                'identity_mode': distribution.get('identity_mode'),
                'identity_key': distribution.get('qualified_name') or distribution.get('name'),
                'version': distribution.get('version'),
                'status': distribution.get('status'),
                'stage': distribution.get('status') or 'archived',
                'path': str((reg_root / distribution.get('manifest_path')).resolve()),
                'skill_path': None,
                'dir_name': Path(distribution.get('manifest_path') or '').parent.name,
                'relative_path': distribution.get('manifest_path'),
                'installable': True,
                'snapshot_of': None,
                'snapshot_created_at': distribution.get('generated_at'),
                'depends_on': distribution.get('depends_on', []),
                'conflicts_with': distribution.get('conflicts_with', []),
                'meta': {'name': distribution.get('name'), 'version': distribution.get('version')},
                'source_type': 'distribution-manifest',
                'distribution_manifest': distribution.get('manifest_path'),
                'distribution_bundle': distribution.get('bundle_path'),
                'distribution_bundle_sha256': distribution.get('bundle_sha256'),
                'distribution_attestation': distribution.get('attestation_path'),
                'distribution_attestation_signature': distribution.get('attestation_signature_path'),
                'source_snapshot_kind': distribution.get('source_snapshot_kind'),
                'source_snapshot_tag': distribution.get('source_snapshot_tag'),
                'source_snapshot_ref': distribution.get('source_snapshot_ref'),
                'source_snapshot_commit': distribution.get('source_snapshot_commit'),
                'registry_commit': distribution.get('source_snapshot_commit') or registry_state.get('registry_commit'),
                'registry_tag': distribution.get('source_snapshot_tag') or registry_state.get('registry_tag'),
                'registry_ref': distribution.get('source_snapshot_ref') or registry_state.get('registry_ref'),
                'registry_priority': int(reg.get('priority', 0)),
                'registry_order': index,
                'registry_enabled': reg.get('enabled', True),
            })
    by_name = {}
    by_identity = {}
    for candidate in candidates:
        by_name.setdefault(candidate.get('name'), []).append(candidate)
        by_identity.setdefault(candidate.get('identity_key') or candidate.get('name'), []).append(candidate)
    for name in list(by_name):
        by_name[name] = sorted(by_name[name], key=cmp_to_key(_candidate_catalog_compare))
    for key in list(by_identity):
        by_identity[key] = sorted(by_identity[key], key=cmp_to_key(_candidate_catalog_compare))
    return {
        'config': cfg,
        'registries': sorted_registries,
        'registry_roots': registry_roots,
        'registry_identities': registry_identities,
        'missing_roots': missing_roots,
        'candidates': candidates,
        'by_name': by_name,
        'by_identity': by_identity,
    }


def _candidate_catalog_compare(left, right):
    if left['registry_priority'] != right['registry_priority']:
        return -1 if left['registry_priority'] > right['registry_priority'] else 1
    left_source = 0 if left.get('source_type') == 'distribution-manifest' else 1
    right_source = 0 if right.get('source_type') == 'distribution-manifest' else 1
    if left_source != right_source:
        return -1 if left_source < right_source else 1
    stage_order = {'active': 0, 'incubating': 1, 'archived': 2}
    left_stage = stage_order.get(left.get('stage'), 9)
    right_stage = stage_order.get(right.get('stage'), 9)
    if left_stage != right_stage:
        return -1 if left_stage < right_stage else 1
    version_cmp = compare_versions(right.get('version') or '0.0.0', left.get('version') or '0.0.0')
    if version_cmp:
        return version_cmp
    left_snapshot = left.get('snapshot_created_at') or ''
    right_snapshot = right.get('snapshot_created_at') or ''
    if left_snapshot != right_snapshot:
        return -1 if left_snapshot > right_snapshot else 1
    left_key = (left.get('registry_name') or '', left.get('dir_name') or '', left.get('path') or '')
    right_key = (right.get('registry_name') or '', right.get('dir_name') or '', right.get('path') or '')
    if left_key == right_key:
        return 0
    return -1 if left_key < right_key else 1


def load_installed_state(target_dir):
    target = Path(target_dir)
    try:
        manifest = load_install_manifest(target, allow_missing=True)
    except InstallManifestError as exc:
        raise DependencyError(str(exc)) from exc
    installed = {}
    manifest_skills = manifest.get('skills') or {}
    if target.exists():
        for child in sorted(path for path in target.iterdir() if path.is_dir() and (path / '_meta.json').exists()):
            meta = load_meta(child / '_meta.json')
            normalized = normalize_meta_dependencies(meta)
            identity = normalize_skill_identity(meta)
            identity_key = identity_key_for(identity) or meta.get('name') or child.name
            entry = {}
            for key in unique([identity_key, meta.get('name'), child.name]):
                if key and key in manifest_skills:
                    entry = manifest_skills.get(key) or {}
                    break
            installed[identity_key] = {
                **identity,
                'name': meta.get('name'),
                'publisher': identity.get('publisher'),
                'qualified_name': identity.get('qualified_name'),
                'identity_mode': identity.get('identity_mode'),
                'identity_key': identity_key,
                'version': meta.get('version') or entry.get('version'),
                'locked_version': entry.get('locked_version') or meta.get('version'),
                'source_registry': entry.get('source_registry'),
                'path': str(child),
                'meta': meta,
                'depends_on': normalized['depends_on'],
                'conflicts_with': normalized['conflicts_with'],
            }
    for name, entry in manifest_skills.items():
        identity_key = entry.get('qualified_name') or entry.get('name') or name
        if identity_key in installed:
            continue
        installed[identity_key] = {
            'name': entry.get('name') or name,
            'publisher': entry.get('publisher'),
            'qualified_name': entry.get('qualified_name'),
            'identity_mode': entry.get('identity_mode') or ('qualified' if entry.get('qualified_name') else 'legacy'),
            'identity_key': identity_key,
            'version': entry.get('version') or entry.get('locked_version'),
            'locked_version': entry.get('locked_version'),
            'source_registry': entry.get('source_registry'),
            'path': str((target / (entry.get('name') or name)).resolve()),
            'meta': None,
            'depends_on': [],
            'conflicts_with': [],
        }
    return installed


def candidate_from_skill_dir(skill_dir, source_registry=None, source_info=None):
    skill_path = Path(skill_dir).resolve()
    meta = load_meta(skill_path / '_meta.json')
    normalized = normalize_meta_dependencies(meta)
    identity = normalize_skill_identity(meta)
    info = source_info or {}
    return {
        **info,
        **identity,
        'name': meta.get('name'),
        'publisher': identity.get('publisher'),
        'qualified_name': identity.get('qualified_name'),
        'identity_mode': identity.get('identity_mode'),
        'identity_key': identity_key_for(identity) or meta.get('name'),
        'version': meta.get('version'),
        'status': meta.get('status'),
        'stage': info.get('stage') or skill_path.parent.name,
        'path': str(skill_path),
        'skill_path': str(skill_path),
        'dir_name': skill_path.name,
        'relative_path': info.get('relative_path'),
        'installable': bool(meta.get('distribution', {}).get('installable', True)),
        'snapshot_of': meta.get('snapshot_of'),
        'snapshot_created_at': meta.get('snapshot_created_at'),
        'depends_on': normalized['depends_on'],
        'conflicts_with': normalized['conflicts_with'],
        'meta': meta,
        'registry_name': source_registry or info.get('registry_name') or info.get('source_registry') or 'self',
        'registry_priority': int(info.get('registry_priority', 0) or 0),
        'source_type': info.get('source_type') or 'working-tree',
        'distribution_manifest': info.get('distribution_manifest'),
        'distribution_bundle': info.get('distribution_bundle'),
        'distribution_bundle_sha256': info.get('distribution_bundle_sha256'),
        'distribution_attestation': info.get('distribution_attestation'),
        'distribution_attestation_signature': info.get('distribution_attestation_signature'),
        'source_snapshot_kind': info.get('source_snapshot_kind'),
        'source_snapshot_tag': info.get('source_snapshot_tag'),
        'source_snapshot_ref': info.get('source_snapshot_ref'),
        'source_snapshot_commit': info.get('source_snapshot_commit'),
    }


def entry_matches_skill(entry, skill):
    if entry.get('qualified_name'):
        if entry.get('qualified_name') != skill.get('qualified_name'):
            return False
    else:
        if entry.get('name') != skill.get('name'):
            return False
        if entry.get('publisher') and entry.get('publisher') != skill.get('publisher'):
            return False
    if entry.get('registry') and entry.get('registry') != skill.get('registry_name'):
        return False
    version = skill.get('version')
    if not version:
        return False
    return version_satisfies(version, entry.get('version') or '*')


def constraints_compatible(constraints):
    registries = unique([entry.get('registry') for entry in constraints if entry.get('registry')])
    if len(registries) > 1:
        return False, f'conflicting registry hints: {", ".join(registries)}'
    return True, None


def installed_identity_matches(candidate, installed):
    if not installed:
        return False
    candidate_identity = candidate.get('identity_key') or candidate.get('qualified_name') or candidate.get('name')
    installed_identity = installed.get('identity_key') or installed.get('qualified_name') or installed.get('name')
    if candidate_identity and installed_identity and candidate_identity != installed_identity:
        return False
    installed_version = installed.get('version') or installed.get('locked_version')
    if installed_version and candidate.get('version') != installed_version:
        return False
    installed_registry = installed.get('source_registry')
    if installed_registry and candidate.get('registry_name') != installed_registry:
        return False
    return True


class DependencyPlanner:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.catalog = scan_enabled_registry_skills(self.root)

    def plan(self, root_candidate, target_dir=None, mode='install'):
        installed = load_installed_state(target_dir) if target_dir else {}
        root_key = root_candidate.get('identity_key') or root_candidate.get('name')
        selected = {root_key: root_candidate}
        pending = [self._prepare_requirement(root_candidate, entry) for entry in root_candidate.get('depends_on', [])]
        result = self._resolve_recursive(selected, pending, installed)
        self._validate_final_state(root_candidate, result, installed, mode)
        return self._build_plan(root_candidate, result, installed, mode)

    def _prepare_requirement(self, source_candidate, entry):
        return {
            **entry,
            'source_name': source_candidate.get('name'),
            'source_qualified_name': source_candidate.get('qualified_name'),
            'source_version': source_candidate.get('version'),
            'source_registry': source_candidate.get('registry_name'),
        }

    def _resolve_recursive(self, selected, pending, installed):
        if not pending:
            return selected

        pending_sorted = sorted(
            pending,
            key=lambda item: (
                item.get('identity_key') or item.get('name') or '',
                item.get('registry') or '',
                item.get('version') or '*',
                item.get('source_name') or '',
                item.get('source_version') or '',
            ),
        )
        requirement = pending_sorted[0]
        identity_key = requirement.get('identity_key') or requirement.get('name')
        display_name = display_identity(requirement) or requirement.get('name')
        remaining = pending_sorted[1:]
        same_name = [requirement]
        rest = []
        for item in remaining:
            if (item.get('identity_key') or item.get('name')) == identity_key:
                same_name.append(item)
            else:
                rest.append(item)

        okay, problem = constraints_compatible(same_name)
        if not okay:
            raise DependencyError(
                f'conflicting requirements for {display_name}',
                {
                    'skill': display_name,
                    'constraints': same_name,
                    'reason': problem,
                },
            )

        if identity_key in selected:
            candidate = selected[identity_key]
            if not self._candidate_satisfies_all(candidate, same_name):
                raise DependencyError(
                    f'selected dependency no longer satisfies all constraints for {display_name}',
                    {
                        'skill': display_name,
                        'selected': self._candidate_view(candidate),
                        'constraints': same_name,
                    },
                )
            return self._resolve_recursive(selected, rest, installed)

        matching_candidates = self._matching_candidates(requirement, same_name, installed.get(identity_key))
        if not matching_candidates:
            available = [self._candidate_view(item) for item in self.catalog['by_identity'].get(identity_key, [])]
            raise DependencyError(
                f'no registry candidate satisfies dependency {display_name}',
                {
                    'skill': display_name,
                    'constraints': same_name,
                    'available': available,
                    'missing_registry_roots': self.catalog.get('missing_roots', {}),
                },
            )

        rejected = []
        for candidate in matching_candidates:
            conflict = self._selected_conflict(candidate, selected)
            if conflict:
                rejected.append({'candidate': self._candidate_view(candidate), 'reason': conflict})
                continue
            next_selected = dict(selected)
            next_selected[candidate.get('identity_key') or candidate.get('name')] = candidate
            next_pending = list(rest)
            for dep in candidate.get('depends_on', []):
                next_pending.append(self._prepare_requirement(candidate, dep))
            try:
                return self._resolve_recursive(next_selected, next_pending, installed)
            except DependencyError as exc:
                rejected.append({'candidate': self._candidate_view(candidate), 'reason': exc.message})

        raise DependencyError(
            f'no compatible resolution path found for {display_name}',
            {
                'skill': display_name,
                'constraints': same_name,
                'rejected_candidates': rejected,
            },
        )

    def _candidate_satisfies_all(self, candidate, constraints):
        for entry in constraints:
            if entry.get('registry') and entry.get('registry') != candidate.get('registry_name'):
                return False
            if candidate.get('stage') == 'incubating' and not entry.get('allow_incubating'):
                return False
            if candidate.get('stage') == 'archived' and not constraint_is_exact(entry.get('version') or '*'):
                return False
            if not version_satisfies(candidate.get('version') or '0.0.0', entry.get('version') or '*'):
                return False
        return bool(candidate.get('installable', True))

    def _preferred_registries(self, constraints):
        explicit = unique([entry.get('registry') for entry in constraints if entry.get('registry')])
        if explicit:
            return explicit
        from_sources = unique([entry.get('source_registry') for entry in constraints if entry.get('source_registry')])
        configured = [reg.get('name') for reg in self.catalog.get('registries', [])]
        return unique(from_sources + configured)

    def _matching_candidates(self, requirement, constraints, installed_item):
        preferred = self._preferred_registries(constraints)
        candidates = []
        identity_key = requirement.get('identity_key') or requirement.get('name')
        candidate_pool = self.catalog['by_identity'].get(identity_key, self.catalog['by_name'].get(requirement.get('name'), []))
        for candidate in candidate_pool:
            if self._candidate_satisfies_all(candidate, constraints):
                candidates.append(candidate)

        exact_only = all(constraint_is_exact(entry.get('version') or '*') for entry in constraints)

        def compare(left, right):
            left_installed = 0 if installed_identity_matches(left, installed_item) else 1
            right_installed = 0 if installed_identity_matches(right, installed_item) else 1
            if left_installed != right_installed:
                return -1 if left_installed < right_installed else 1
            left_registry = preferred.index(left.get('registry_name')) if left.get('registry_name') in preferred else len(preferred) + left.get('registry_order', 0)
            right_registry = preferred.index(right.get('registry_name')) if right.get('registry_name') in preferred else len(preferred) + right.get('registry_order', 0)
            if left_registry != right_registry:
                return -1 if left_registry < right_registry else 1
            left_source = 0 if left.get('source_type') == 'distribution-manifest' else 1
            right_source = 0 if right.get('source_type') == 'distribution-manifest' else 1
            if left_source != right_source:
                return -1 if left_source < right_source else 1
            stage_order = {'archived': 0, 'active': 1, 'incubating': 2} if exact_only else {'active': 0, 'incubating': 1, 'archived': 2}
            left_stage = stage_order.get(left.get('stage'), 9)
            right_stage = stage_order.get(right.get('stage'), 9)
            if left_stage != right_stage:
                return -1 if left_stage < right_stage else 1
            version_cmp = compare_versions(right.get('version') or '0.0.0', left.get('version') or '0.0.0')
            if version_cmp:
                return version_cmp
            left_snapshot = left.get('snapshot_created_at') or ''
            right_snapshot = right.get('snapshot_created_at') or ''
            if left_snapshot != right_snapshot:
                return -1 if left_snapshot > right_snapshot else 1
            left_key = (left.get('registry_name') or '', left.get('dir_name') or '', left.get('path') or '')
            right_key = (right.get('registry_name') or '', right.get('dir_name') or '', right.get('path') or '')
            if left_key == right_key:
                return 0
            return -1 if left_key < right_key else 1

        return sorted(candidates, key=cmp_to_key(compare))

    def _selected_conflict(self, candidate, selected):
        candidate_identity = candidate.get('identity_key') or candidate.get('name')
        for other_identity, other in selected.items():
            if other_identity == candidate_identity:
                continue
            if other.get('name') == candidate.get('name'):
                return (
                    f'cannot select both {display_identity(other)} and {display_identity(candidate)} '
                    'because installed skill state is still keyed by bare skill name'
                )
            for conflict in candidate.get('conflicts_with', []):
                if entry_matches_skill(conflict, other):
                    return f'{candidate.get("name")} conflicts with selected {other.get("name")} ({constraint_display(conflict)})'
            for conflict in other.get('conflicts_with', []):
                if entry_matches_skill(conflict, candidate):
                    return f'selected {other.get("name")} conflicts with {candidate.get("name")} ({constraint_display(conflict)})'
        return None

    def _validate_final_state(self, root_candidate, selected, installed, mode):
        selected_names = set(selected)
        for candidate in selected.values():
            for installed_item in installed.values():
                if (installed_item.get('identity_key') or installed_item.get('name')) in selected_names:
                    continue
                for conflict in candidate.get('conflicts_with', []):
                    if entry_matches_skill(conflict, installed_item):
                        raise DependencyError(
                            f'{candidate.get("name")} conflicts with already installed {installed_item.get("name")}',
                            {
                                'skill': candidate.get('name'),
                                'selected': self._candidate_view(candidate),
                                'installed': self._installed_view(installed_item),
                                'conflict': conflict,
                            },
                        )
                for conflict in installed_item.get('conflicts_with', []):
                    if entry_matches_skill(conflict, candidate):
                        raise DependencyError(
                            f'already installed {installed_item.get("name")} conflicts with {candidate.get("name")}',
                            {
                                'skill': candidate.get('name'),
                                'selected': self._candidate_view(candidate),
                                'installed': self._installed_view(installed_item),
                                'conflict': conflict,
                            },
                        )
        root_identity = root_candidate.get('identity_key') or root_candidate.get('name')
        for identity_key, candidate in selected.items():
            installed_item = installed.get(identity_key)
            if not installed_item:
                continue
            if mode == 'install' and identity_key == root_identity:
                continue
            locked_version = installed_item.get('locked_version')
            if locked_version and candidate.get('version') != locked_version:
                raise DependencyError(
                    f'unsafe upgrade plan for {display_identity(candidate) or identity_key}: installed copy is locked to {locked_version}',
                    {
                        'skill': display_identity(candidate) or identity_key,
                        'selected': self._candidate_view(candidate),
                        'installed': self._installed_view(installed_item),
                        'reason': 'locked-version-mismatch',
                    },
                )

    def _candidate_view(self, candidate):
        return {
            'name': candidate.get('name'),
            'publisher': candidate.get('publisher'),
            'qualified_name': candidate.get('qualified_name'),
            'version': candidate.get('version'),
            'registry': candidate.get('registry_name'),
            'stage': candidate.get('stage'),
            'path': candidate.get('path'),
            'source_type': candidate.get('source_type'),
            'distribution_manifest': candidate.get('distribution_manifest'),
            'source_snapshot_tag': candidate.get('source_snapshot_tag'),
            'source_snapshot_commit': candidate.get('source_snapshot_commit'),
        }

    def _installed_view(self, installed):
        return {
            'name': installed.get('name'),
            'publisher': installed.get('publisher'),
            'qualified_name': installed.get('qualified_name'),
            'version': installed.get('version'),
            'locked_version': installed.get('locked_version'),
            'registry': installed.get('source_registry'),
            'path': installed.get('path'),
        }

    def _build_plan(self, root_candidate, selected, installed, mode):
        apply_order = []
        visited = set()

        def visit(identity_key):
            if identity_key in visited:
                return
            visited.add(identity_key)
            candidate = selected[identity_key]
            deps = sorted(candidate.get('depends_on', []), key=lambda item: (item.get('name') or '', item.get('version') or '*'))
            for dep in deps:
                dep_key = dep.get('identity_key') or dep.get('name')
                if dep_key in selected:
                    visit(dep_key)
            apply_order.append(identity_key)

        root_identity = root_candidate.get('identity_key') or root_candidate.get('name')
        visit(root_identity)
        requesters = {}
        for candidate in selected.values():
            for dep in candidate.get('depends_on', []):
                dep_key = dep.get('identity_key') or dep.get('name')
                requesters.setdefault(dep_key, []).append({
                    'by': candidate.get('name'),
                    'by_qualified_name': candidate.get('qualified_name'),
                    'version': candidate.get('version'),
                    'registry': dep.get('registry'),
                    'constraint': dep.get('version'),
                    'allow_incubating': dep.get('allow_incubating', False),
                })

        steps = []
        for index, identity_key in enumerate(apply_order, start=1):
            candidate = selected[identity_key]
            installed_item = installed.get(identity_key)
            action = self._plan_action(identity_key, candidate, installed_item, root_candidate, mode)
            steps.append({
                'order': index,
                'name': candidate.get('name'),
                'publisher': candidate.get('publisher'),
                'qualified_name': candidate.get('qualified_name'),
                'identity_mode': candidate.get('identity_mode'),
                'version': candidate.get('version'),
                'registry': candidate.get('registry_name'),
                'stage': candidate.get('stage'),
                'path': candidate.get('path'),
                'skill_path': candidate.get('skill_path'),
                'relative_path': candidate.get('relative_path'),
                'source_type': candidate.get('source_type'),
                'distribution_manifest': candidate.get('distribution_manifest'),
                'distribution_bundle': candidate.get('distribution_bundle'),
                'distribution_bundle_sha256': candidate.get('distribution_bundle_sha256'),
                'distribution_attestation': candidate.get('distribution_attestation'),
                'distribution_attestation_signature': candidate.get('distribution_attestation_signature'),
                'action': action,
                'needs_apply': action not in {'keep'},
                'requested_by': requesters.get(identity_key, []),
                'depends_on': candidate.get('depends_on', []),
                'conflicts_with': candidate.get('conflicts_with', []),
                'root': identity_key == root_identity,
                'source_commit': candidate.get('registry_commit'),
                'source_ref': candidate.get('registry_ref'),
                'source_tag': candidate.get('registry_tag'),
                'source_snapshot_kind': candidate.get('source_snapshot_kind'),
                'source_snapshot_tag': candidate.get('source_snapshot_tag'),
                'source_snapshot_ref': candidate.get('source_snapshot_ref'),
                'source_snapshot_commit': candidate.get('source_snapshot_commit'),
            })
        return {
            'mode': mode,
            'root': self._candidate_view(root_candidate),
            'steps': steps,
            'registries_consulted': [reg.get('name') for reg in self.catalog.get('registries', [])],
        }

    def _plan_action(self, name, candidate, installed_item, root_candidate, mode):
        root_identity = root_candidate.get('identity_key') or root_candidate.get('name')
        if not installed_item:
            return 'sync' if name == root_identity and mode == 'sync' else 'install'
        same_version = installed_item.get('version') == candidate.get('version') or installed_item.get('locked_version') == candidate.get('version')
        same_registry = not installed_item.get('source_registry') or installed_item.get('source_registry') == candidate.get('registry_name')
        if name == root_identity and mode == 'sync':
            return 'sync' if not (same_version and same_registry) else 'keep'
        if same_version and same_registry:
            return 'keep'
        if same_version and not same_registry:
            return 'switch'
        if not same_version and same_registry:
            return 'upgrade'
        return 'switch-upgrade'


def plan_from_skill_dir(skill_dir, target_dir=None, source_registry=None, source_info=None, mode='install'):
    planner = DependencyPlanner(ROOT)
    root_candidate = candidate_from_skill_dir(skill_dir, source_registry=source_registry, source_info=source_info)
    return planner.plan(root_candidate, target_dir=target_dir, mode=mode)


def error_to_payload(error):
    payload = {'error': error.message}
    payload.update(error.details or {})
    return payload


def plan_to_text(plan):
    lines = []
    root = plan.get('root') or {}
    root_display = root.get('qualified_name') or root.get('name')
    lines.append(f"resolution plan: {root_display}@{root.get('version')} from {root.get('registry')}")
    for step in plan.get('steps', []):
        action = step.get('action')
        stage = step.get('stage')
        registry = step.get('registry')
        display = step.get('qualified_name') or step.get('name')
        head = f"- [{action}] {display}@{step.get('version')} ({stage}) from {registry}"
        if step.get('source_commit'):
            head += f" @{step.get('source_commit')[:12]}"
        elif step.get('source_tag'):
            head += f" tag={step.get('source_tag')}"
        elif step.get('source_ref'):
            head += f" ref={step.get('source_ref')}"
        lines.append(head)
        for requester in step.get('requested_by', []):
            requester_name = requester.get('by_qualified_name') or requester.get('by')
            lines.append(
                f"    requested by {requester_name}@{requester.get('version')} -> {requester.get('constraint')}"
                + (f" [{requester.get('registry')}]" if requester.get('registry') else '')
                + (' +incubating' if requester.get('allow_incubating') else '')
            )
    return '\n'.join(lines)
