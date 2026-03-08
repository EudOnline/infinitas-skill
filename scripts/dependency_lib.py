#!/usr/bin/env python3
import json
import re
from functools import cmp_to_key
from pathlib import Path

from registry_source_lib import load_registry_config, registry_identity, resolve_registry_root

ROOT = Path(__file__).resolve().parent.parent
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
        if not LEGACY_REF_RE.match(entry):
            raise DependencyError(f'invalid {field} ref {entry!r}')
        name, _, version = entry.partition('@')
        normalized = {
            'name': name,
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
        if not isinstance(name, str) or not SKILL_NAME_RE.match(name):
            raise DependencyError(f'{field} entry has invalid name {name!r}')
        version = entry.get('version', '*')
        if not isinstance(version, str):
            raise DependencyError(f'{field} entry for {name} has non-string version constraint')
        registry = entry.get('registry')
        if registry is not None and (not isinstance(registry, str) or not registry.strip()):
            raise DependencyError(f'{field} entry for {name} has invalid registry hint {registry!r}')
        allow_incubating = entry.get('allow_incubating', False)
        if not isinstance(allow_incubating, bool):
            raise DependencyError(f'{field} entry for {name} has non-boolean allow_incubating')
        normalized = {
            'name': name,
            'version': canonicalize_constraint(version),
            'registry': registry.strip() if isinstance(registry, str) and registry.strip() else None,
            'allow_incubating': allow_incubating,
            'format': 'object',
            'raw': entry,
        }
    else:
        raise DependencyError(f'{field} entries must be strings or objects')

    if owner_name and normalized['name'] == owner_name:
        raise DependencyError(f'{field} cannot reference itself ({normalized["name"]})')
    return normalized


def normalize_meta_dependencies(meta, owner_name=None):
    owner = owner_name or meta.get('name')
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
    return f'{entry["name"]}{registry} {version}{incubating}'.strip()


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
        identity = registry_identity(root, reg)
        registry_identities[reg_name] = identity
        skills_root = reg_root / 'skills'
        for stage in ['active', 'incubating', 'archived']:
            stage_dir = skills_root / stage
            if not stage_dir.exists():
                continue
            for skill_dir in sorted(path for path in stage_dir.iterdir() if path.is_dir() and (path / '_meta.json').exists()):
                meta = load_meta(skill_dir / '_meta.json')
                normalized = normalize_meta_dependencies(meta)
                candidates.append({
                    **identity,
                    'name': meta.get('name'),
                    'version': meta.get('version'),
                    'status': meta.get('status'),
                    'stage': stage,
                    'path': str(skill_dir),
                    'dir_name': skill_dir.name,
                    'relative_path': str(skill_dir.relative_to(reg_root)),
                    'installable': bool(meta.get('distribution', {}).get('installable', True)),
                    'snapshot_of': meta.get('snapshot_of'),
                    'snapshot_created_at': meta.get('snapshot_created_at'),
                    'depends_on': normalized['depends_on'],
                    'conflicts_with': normalized['conflicts_with'],
                    'meta': meta,
                    'registry_priority': int(reg.get('priority', 0)),
                    'registry_order': index,
                    'registry_enabled': reg.get('enabled', True),
                })
    by_name = {}
    for candidate in candidates:
        by_name.setdefault(candidate.get('name'), []).append(candidate)
    for name in list(by_name):
        by_name[name] = sorted(by_name[name], key=cmp_to_key(_candidate_catalog_compare))
    return {
        'config': cfg,
        'registries': sorted_registries,
        'registry_roots': registry_roots,
        'registry_identities': registry_identities,
        'missing_roots': missing_roots,
        'candidates': candidates,
        'by_name': by_name,
    }


def _candidate_catalog_compare(left, right):
    if left['registry_priority'] != right['registry_priority']:
        return -1 if left['registry_priority'] > right['registry_priority'] else 1
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
    manifest_path = target / '.infinitas-skill-install-manifest.json'
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    installed = {}
    manifest_skills = (manifest.get('skills') or {}) if isinstance(manifest, dict) else {}
    if target.exists():
        for child in sorted(path for path in target.iterdir() if path.is_dir() and (path / '_meta.json').exists()):
            meta = load_meta(child / '_meta.json')
            normalized = normalize_meta_dependencies(meta)
            entry = manifest_skills.get(meta.get('name')) or manifest_skills.get(child.name) or {}
            installed[meta.get('name')] = {
                'name': meta.get('name'),
                'version': meta.get('version') or entry.get('version'),
                'locked_version': entry.get('locked_version') or meta.get('version'),
                'source_registry': entry.get('source_registry'),
                'path': str(child),
                'meta': meta,
                'depends_on': normalized['depends_on'],
                'conflicts_with': normalized['conflicts_with'],
            }
    for name, entry in manifest_skills.items():
        if name in installed:
            continue
        installed[name] = {
            'name': name,
            'version': entry.get('version') or entry.get('locked_version'),
            'locked_version': entry.get('locked_version'),
            'source_registry': entry.get('source_registry'),
            'path': str((target / name).resolve()),
            'meta': None,
            'depends_on': [],
            'conflicts_with': [],
        }
    return installed


def candidate_from_skill_dir(skill_dir, source_registry=None, source_info=None):
    skill_path = Path(skill_dir).resolve()
    meta = load_meta(skill_path / '_meta.json')
    normalized = normalize_meta_dependencies(meta)
    info = source_info or {}
    return {
        **info,
        'name': meta.get('name'),
        'version': meta.get('version'),
        'status': meta.get('status'),
        'stage': info.get('stage') or skill_path.parent.name,
        'path': str(skill_path),
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
    }


def entry_matches_skill(entry, skill):
    if entry.get('name') != skill.get('name'):
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
        selected = {root_candidate['name']: root_candidate}
        pending = [self._prepare_requirement(root_candidate, entry) for entry in root_candidate.get('depends_on', [])]
        result = self._resolve_recursive(selected, pending, installed)
        self._validate_final_state(root_candidate, result, installed, mode)
        return self._build_plan(root_candidate, result, installed, mode)

    def _prepare_requirement(self, source_candidate, entry):
        return {
            **entry,
            'source_name': source_candidate.get('name'),
            'source_version': source_candidate.get('version'),
            'source_registry': source_candidate.get('registry_name'),
        }

    def _resolve_recursive(self, selected, pending, installed):
        if not pending:
            return selected

        pending_sorted = sorted(
            pending,
            key=lambda item: (
                item.get('name') or '',
                item.get('registry') or '',
                item.get('version') or '*',
                item.get('source_name') or '',
                item.get('source_version') or '',
            ),
        )
        requirement = pending_sorted[0]
        name = requirement['name']
        remaining = pending_sorted[1:]
        same_name = [requirement]
        rest = []
        for item in remaining:
            if item['name'] == name:
                same_name.append(item)
            else:
                rest.append(item)

        okay, problem = constraints_compatible(same_name)
        if not okay:
            raise DependencyError(
                f'conflicting requirements for {name}',
                {
                    'skill': name,
                    'constraints': same_name,
                    'reason': problem,
                },
            )

        if name in selected:
            candidate = selected[name]
            if not self._candidate_satisfies_all(candidate, same_name):
                raise DependencyError(
                    f'selected dependency no longer satisfies all constraints for {name}',
                    {
                        'skill': name,
                        'selected': self._candidate_view(candidate),
                        'constraints': same_name,
                    },
                )
            return self._resolve_recursive(selected, rest, installed)

        matching_candidates = self._matching_candidates(name, same_name, installed.get(name))
        if not matching_candidates:
            available = [self._candidate_view(item) for item in self.catalog['by_name'].get(name, [])]
            raise DependencyError(
                f'no registry candidate satisfies dependency {name}',
                {
                    'skill': name,
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
            next_selected[name] = candidate
            next_pending = list(rest)
            for dep in candidate.get('depends_on', []):
                next_pending.append(self._prepare_requirement(candidate, dep))
            try:
                return self._resolve_recursive(next_selected, next_pending, installed)
            except DependencyError as exc:
                rejected.append({'candidate': self._candidate_view(candidate), 'reason': exc.message})

        raise DependencyError(
            f'no compatible resolution path found for {name}',
            {
                'skill': name,
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

    def _matching_candidates(self, name, constraints, installed_item):
        preferred = self._preferred_registries(constraints)
        candidates = []
        for candidate in self.catalog['by_name'].get(name, []):
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
        for other_name, other in selected.items():
            if other_name == candidate.get('name'):
                continue
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
                if installed_item.get('name') in selected_names:
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
        for name, candidate in selected.items():
            installed_item = installed.get(name)
            if not installed_item:
                continue
            if mode == 'install' and name == root_candidate.get('name'):
                continue
            locked_version = installed_item.get('locked_version')
            if locked_version and candidate.get('version') != locked_version:
                raise DependencyError(
                    f'unsafe upgrade plan for {name}: installed copy is locked to {locked_version}',
                    {
                        'skill': name,
                        'selected': self._candidate_view(candidate),
                        'installed': self._installed_view(installed_item),
                        'reason': 'locked-version-mismatch',
                    },
                )

    def _candidate_view(self, candidate):
        return {
            'name': candidate.get('name'),
            'version': candidate.get('version'),
            'registry': candidate.get('registry_name'),
            'stage': candidate.get('stage'),
            'path': candidate.get('path'),
        }

    def _installed_view(self, installed):
        return {
            'name': installed.get('name'),
            'version': installed.get('version'),
            'locked_version': installed.get('locked_version'),
            'registry': installed.get('source_registry'),
            'path': installed.get('path'),
        }

    def _build_plan(self, root_candidate, selected, installed, mode):
        apply_order = []
        visited = set()

        def visit(name):
            if name in visited:
                return
            visited.add(name)
            candidate = selected[name]
            deps = sorted(candidate.get('depends_on', []), key=lambda item: (item.get('name') or '', item.get('version') or '*'))
            for dep in deps:
                if dep.get('name') in selected:
                    visit(dep['name'])
            apply_order.append(name)

        visit(root_candidate['name'])
        requesters = {}
        for candidate in selected.values():
            for dep in candidate.get('depends_on', []):
                requesters.setdefault(dep['name'], []).append({
                    'by': candidate.get('name'),
                    'version': candidate.get('version'),
                    'registry': dep.get('registry'),
                    'constraint': dep.get('version'),
                    'allow_incubating': dep.get('allow_incubating', False),
                })

        steps = []
        for index, name in enumerate(apply_order, start=1):
            candidate = selected[name]
            installed_item = installed.get(name)
            action = self._plan_action(name, candidate, installed_item, root_candidate, mode)
            steps.append({
                'order': index,
                'name': candidate.get('name'),
                'version': candidate.get('version'),
                'registry': candidate.get('registry_name'),
                'stage': candidate.get('stage'),
                'path': candidate.get('path'),
                'relative_path': candidate.get('relative_path'),
                'action': action,
                'needs_apply': action not in {'keep'},
                'requested_by': requesters.get(name, []),
                'depends_on': candidate.get('depends_on', []),
                'conflicts_with': candidate.get('conflicts_with', []),
                'root': name == root_candidate.get('name'),
                'source_commit': candidate.get('registry_commit'),
                'source_ref': candidate.get('registry_ref'),
                'source_tag': candidate.get('registry_tag'),
            })
        return {
            'mode': mode,
            'root': self._candidate_view(root_candidate),
            'steps': steps,
            'registries_consulted': [reg.get('name') for reg in self.catalog.get('registries', [])],
        }

    def _plan_action(self, name, candidate, installed_item, root_candidate, mode):
        if not installed_item:
            return 'sync' if name == root_candidate.get('name') and mode == 'sync' else 'install'
        same_version = installed_item.get('version') == candidate.get('version') or installed_item.get('locked_version') == candidate.get('version')
        same_registry = not installed_item.get('source_registry') or installed_item.get('source_registry') == candidate.get('registry_name')
        if name == root_candidate.get('name') and mode == 'sync':
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
    lines.append(f"resolution plan: {root.get('name')}@{root.get('version')} from {root.get('registry')}")
    for step in plan.get('steps', []):
        action = step.get('action')
        stage = step.get('stage')
        registry = step.get('registry')
        head = f"- [{action}] {step.get('name')}@{step.get('version')} ({stage}) from {registry}"
        if step.get('source_commit'):
            head += f" @{step.get('source_commit')[:12]}"
        elif step.get('source_tag'):
            head += f" tag={step.get('source_tag')}"
        elif step.get('source_ref'):
            head += f" ref={step.get('source_ref')}"
        lines.append(head)
        for requester in step.get('requested_by', []):
            lines.append(
                f"    requested by {requester.get('by')}@{requester.get('version')} -> {requester.get('constraint')}"
                + (f" [{requester.get('registry')}]" if requester.get('registry') else '')
                + (' +incubating' if requester.get('allow_incubating') else '')
            )
    return '\n'.join(lines)
