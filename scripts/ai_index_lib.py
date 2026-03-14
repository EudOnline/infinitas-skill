#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SEMVER_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:[-+]([A-Za-z0-9_.-]+))?$')

INSTALL_POLICY = {
    'mode': 'immutable-only',
    'direct_source_install_allowed': False,
    'require_attestation': True,
    'require_sha256': True,
}

OPENCLAW_INTEROP = {
    'runtime_targets': ['~/.openclaw/skills', '~/.openclaw/workspace/skills'],
    'import_supported': True,
    'export_supported': True,
    'public_publish': {
        'clawhub': {
            'supported': True,
            'default': False,
        }
    },
}


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _semver_key(value):
    if not isinstance(value, str):
        return (-1, -1, -1, -1, '')
    match = SEMVER_RE.match(value.strip())
    if not match:
        return (-1, -1, -1, -1, value)
    major, minor, patch, suffix = match.groups()
    stability = 1 if suffix is None else 0
    return (int(major), int(minor), int(patch), stability, suffix or '')


def _sort_versions(values):
    unique = []
    for value in values:
        if isinstance(value, str) and value not in unique:
            unique.append(value)
    return sorted(unique, key=_semver_key, reverse=True)


def _relative_repo_path(value):
    if not isinstance(value, str) or not value.strip():
        return False
    return not Path(value).is_absolute()


def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _catalog_entry_by_key(entries):
    lookup = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get('qualified_name') or entry.get('name')
        if not key:
            continue
        current = lookup.get(key)
        if current is None or _semver_key(entry.get('version')) > _semver_key(current.get('version')):
            lookup[key] = entry
    return lookup


def _meta_for_entry(root: Path, entry):
    rel_path = entry.get('path')
    if not isinstance(rel_path, str) or not rel_path:
        return {}
    meta_path = root / rel_path / '_meta.json'
    if not meta_path.exists():
        return {}
    try:
        return _load_json(meta_path)
    except Exception:
        return {}


def _openclaw_interop_payload():
    return {
        'runtime_targets': list(OPENCLAW_INTEROP['runtime_targets']),
        'import_supported': True,
        'export_supported': True,
        'public_publish': {
            'clawhub': {
                'supported': True,
                'default': False,
            }
        },
    }


def _publisher_for_entry(current, meta):
    for candidate in [
        current.get('publisher') if isinstance(current, dict) else None,
        current.get('owner') if isinstance(current, dict) else None,
        meta.get('publisher') if isinstance(meta, dict) else None,
        meta.get('owner') if isinstance(meta, dict) else None,
        meta.get('author') if isinstance(meta, dict) else None,
    ]:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _trust_state_from_version_entry(version_entry):
    if not isinstance(version_entry, dict):
        return 'unknown'
    if version_entry.get('attestation_signature_path'):
        return 'verified'
    if version_entry.get('attestation_path'):
        return 'attested'
    if version_entry.get('installable'):
        return 'installable'
    return 'unknown'


def _maturity_for_entry(meta):
    value = meta.get('maturity') if isinstance(meta, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return 'unknown'


def _quality_score_for_entry(meta):
    value = meta.get('quality_score') if isinstance(meta, dict) else None
    if isinstance(value, int):
        return value
    return 0


def _capabilities_for_entry(meta):
    value = meta.get('capabilities') if isinstance(meta, dict) else None
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    return []


def _last_verified_at(verified_support, meta):
    newest = None
    if isinstance(verified_support, dict):
        for payload in verified_support.values():
            if not isinstance(payload, dict):
                continue
            checked_at = payload.get('checked_at')
            if isinstance(checked_at, str) and checked_at.strip():
                if newest is None or checked_at > newest:
                    newest = checked_at
    if newest:
        return newest
    fallback = meta.get('last_verified_at') if isinstance(meta, dict) else None
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return None


def build_ai_index(*, root: Path, catalog_entries: list, distribution_entries: list) -> dict:
    root = Path(root).resolve()
    catalog_lookup = _catalog_entry_by_key(catalog_entries)
    grouped = {}
    for entry in distribution_entries or []:
        if not isinstance(entry, dict):
            continue
        key = entry.get('qualified_name') or entry.get('name')
        version = entry.get('version')
        if not key or not version:
            continue
        grouped.setdefault(key, []).append(entry)

    skills = []
    for key in sorted(grouped):
        versions = _sort_versions(item.get('version') for item in grouped[key])
        if not versions:
            continue
        current = catalog_lookup.get(key) or grouped[key][0]
        meta = _meta_for_entry(root, current)
        publisher = _publisher_for_entry(current, meta)
        verified_support = current.get('verified_support') or {}
        requires = meta.get('requires') if isinstance(meta.get('requires'), dict) else {}
        entrypoints = meta.get('entrypoints') if isinstance(meta.get('entrypoints'), dict) else {}
        version_map = {}
        for dist in grouped[key]:
            version = dist.get('version')
            if not version:
                continue
            version_map[version] = {
                'manifest_path': dist.get('manifest_path'),
                'distribution_manifest_path': dist.get('manifest_path'),
                'bundle_path': dist.get('bundle_path'),
                'bundle_sha256': dist.get('bundle_sha256'),
                'attestation_path': dist.get('attestation_path'),
                'attestation_signature_path': dist.get('attestation_signature_path'),
                'published_at': dist.get('generated_at'),
                'stability': 'stable',
                'installable': True,
                'attestation_formats': ['ssh', 'ci'] if dist.get('ci_attestation_path') else ['ssh'],
                'trust_state': 'verified' if dist.get('attestation_signature_path') else 'attested',
                'resolution': {
                    'preferred_source': 'distribution-manifest',
                    'fallback_allowed': False,
                },
            }
        latest_version = versions[0]
        latest_entry = version_map[latest_version]
        skills.append(
            {
                'name': current.get('name'),
                'publisher': publisher,
                'qualified_name': current.get('qualified_name') or (f'{publisher}/{current.get("name")}' if publisher and current.get('name') else current.get('name')),
                'summary': current.get('summary') or '',
                'tags': meta.get('tags') or [],
                'maturity': _maturity_for_entry(meta),
                'quality_score': _quality_score_for_entry(meta),
                'capabilities': _capabilities_for_entry(meta),
                'last_verified_at': _last_verified_at(verified_support, meta),
                'use_when': [],
                'avoid_when': [],
                'agent_compatible': current.get('agent_compatible') or [],
                'compatibility': {
                    'declared_support': current.get('declared_support') or current.get('agent_compatible') or [],
                    'verified_support': verified_support,
                },
                'verified_support': verified_support,
                'trust_state': _trust_state_from_version_entry(latest_entry),
                'default_install_version': latest_version,
                'latest_version': latest_version,
                'available_versions': versions,
                'entrypoints': {
                    'skill_md': entrypoints.get('skill_md') or 'SKILL.md',
                },
                'requires': {
                    'tools': requires.get('tools') or [],
                    'env': requires.get('env') or [],
                },
                'interop': {
                    'openclaw': _openclaw_interop_payload(),
                },
                'versions': {version: version_map[version] for version in versions},
            }
        )

    default_registry = None
    for entry in catalog_entries or []:
        if isinstance(entry, dict) and entry.get('source_registry'):
            default_registry = entry.get('source_registry')
            break

    return {
        'schema_version': 1,
        'generated_at': _utc_now_iso(),
        'registry': {
            'default_registry': default_registry,
        },
        'install_policy': dict(INSTALL_POLICY),
        'skills': skills,
    }


def validate_ai_index_payload(payload: dict) -> list:
    errors = []
    if not isinstance(payload, dict):
        return ['ai-index payload must be an object']

    if payload.get('schema_version') != 1:
        errors.append('ai-index schema_version must equal 1')
    if not isinstance(payload.get('generated_at'), str) or not payload.get('generated_at', '').strip():
        errors.append('ai-index generated_at must be a non-empty string')

    registry = payload.get('registry')
    if not isinstance(registry, dict):
        errors.append('ai-index registry must be an object')

    install_policy = payload.get('install_policy')
    if not isinstance(install_policy, dict):
        errors.append('ai-index install_policy must be an object')
    else:
        if install_policy.get('mode') != 'immutable-only':
            errors.append('ai-index install_policy.mode must be immutable-only')
        if install_policy.get('direct_source_install_allowed') is not False:
            errors.append('ai-index direct_source_install_allowed must be false')
        if install_policy.get('require_attestation') is not True:
            errors.append('ai-index require_attestation must be true')
        if install_policy.get('require_sha256') is not True:
            errors.append('ai-index require_sha256 must be true')

    skills = payload.get('skills')
    if not isinstance(skills, list):
        errors.append('ai-index skills must be an array')
        return errors

    for index, skill in enumerate(skills, start=1):
        prefix = f'ai-index skills[{index}]'
        if not isinstance(skill, dict):
            errors.append(f'{prefix} must be an object')
            continue
        for field in ['name', 'qualified_name', 'summary', 'default_install_version', 'latest_version']:
            if not isinstance(skill.get(field), str) or not skill.get(field, '').strip():
                errors.append(f'{prefix}.{field} must be a non-empty string')
        for field in ['use_when', 'avoid_when', 'agent_compatible', 'available_versions', 'tags', 'capabilities']:
            value = skill.get(field)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f'{prefix}.{field} must be an array of strings')
        if not isinstance(skill.get('maturity'), str) or not skill.get('maturity', '').strip():
            errors.append(f'{prefix}.maturity must be a non-empty string')
        if not isinstance(skill.get('quality_score'), int):
            errors.append(f'{prefix}.quality_score must be an integer')
        last_verified_at = skill.get('last_verified_at')
        if last_verified_at is not None and (not isinstance(last_verified_at, str) or not last_verified_at.strip()):
            errors.append(f'{prefix}.last_verified_at must be a non-empty string when present')
        if not isinstance(skill.get('trust_state'), str) or not skill.get('trust_state', '').strip():
            errors.append(f'{prefix}.trust_state must be a non-empty string')
        if not isinstance(skill.get('verified_support'), dict):
            errors.append(f'{prefix}.verified_support must be an object')

        compatibility = skill.get('compatibility')
        if compatibility is not None:
            if not isinstance(compatibility, dict):
                errors.append(f'{prefix}.compatibility must be an object when present')
            else:
                declared_support = compatibility.get('declared_support')
                if not isinstance(declared_support, list) or not all(isinstance(item, str) for item in declared_support):
                    errors.append(f'{prefix}.compatibility.declared_support must be an array of strings')
                verified_support = compatibility.get('verified_support')
                if not isinstance(verified_support, dict):
                    errors.append(f'{prefix}.compatibility.verified_support must be an object')
                else:
                    for platform, payload in verified_support.items():
                        platform_prefix = f'{prefix}.compatibility.verified_support.{platform}'
                        if not isinstance(platform, str) or not platform.strip():
                            errors.append(f'{prefix}.compatibility.verified_support keys must be non-empty strings')
                            continue
                        if not isinstance(payload, dict):
                            errors.append(f'{platform_prefix} must be an object')
                            continue
                        state = payload.get('state')
                        if not isinstance(state, str) or not state.strip():
                            errors.append(f'{platform_prefix}.state must be a non-empty string')
                        for field in ['checked_at', 'checker', 'evidence_path', 'note']:
                            value = payload.get(field)
                            if value is not None and (not isinstance(value, str) or not value.strip()):
                                errors.append(f'{platform_prefix}.{field} must be a non-empty string when present')

        entrypoints = skill.get('entrypoints')
        if not isinstance(entrypoints, dict):
            errors.append(f'{prefix}.entrypoints must be an object')
        else:
            skill_md = entrypoints.get('skill_md')
            if not isinstance(skill_md, str) or not skill_md.strip():
                errors.append(f'{prefix}.entrypoints.skill_md must be a non-empty string')
            elif not _relative_repo_path(skill_md):
                errors.append(f'{prefix}.entrypoints.skill_md must be repo-relative')

        requires = skill.get('requires')
        if not isinstance(requires, dict):
            errors.append(f'{prefix}.requires must be an object')
        else:
            for field in ['tools', 'env']:
                value = requires.get(field)
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    errors.append(f'{prefix}.requires.{field} must be an array of strings')

        interop = skill.get('interop')
        if not isinstance(interop, dict):
            errors.append(f'{prefix}.interop must be an object')
        else:
            openclaw = interop.get('openclaw')
            if not isinstance(openclaw, dict):
                errors.append(f'{prefix}.interop.openclaw must be an object')
            else:
                runtime_targets = openclaw.get('runtime_targets')
                if runtime_targets != OPENCLAW_INTEROP['runtime_targets']:
                    errors.append(f'{prefix}.interop.openclaw.runtime_targets must equal the documented OpenClaw targets')
                if openclaw.get('import_supported') is not True:
                    errors.append(f'{prefix}.interop.openclaw.import_supported must be true')
                if openclaw.get('export_supported') is not True:
                    errors.append(f'{prefix}.interop.openclaw.export_supported must be true')
                public_publish = openclaw.get('public_publish')
                if not isinstance(public_publish, dict):
                    errors.append(f'{prefix}.interop.openclaw.public_publish must be an object')
                else:
                    clawhub = public_publish.get('clawhub')
                    if not isinstance(clawhub, dict):
                        errors.append(f'{prefix}.interop.openclaw.public_publish.clawhub must be an object')
                    else:
                        if clawhub.get('supported') is not True:
                            errors.append(f'{prefix}.interop.openclaw.public_publish.clawhub.supported must be true')
                        if clawhub.get('default') is not False:
                            errors.append(f'{prefix}.interop.openclaw.public_publish.clawhub.default must be false')

        available_versions = skill.get('available_versions') if isinstance(skill.get('available_versions'), list) else []
        versions = skill.get('versions')
        if not isinstance(versions, dict):
            errors.append(f'{prefix}.versions must be an object')
            continue
        default_version = skill.get('default_install_version')
        latest_version = skill.get('latest_version')
        if default_version not in available_versions:
            errors.append(f'{prefix}.default_install_version must exist in available_versions')
        if latest_version not in available_versions:
            errors.append(f'{prefix}.latest_version must exist in available_versions')
        for version in available_versions:
            if version not in versions:
                errors.append(f'{prefix}.available_versions contains {version!r} missing from versions')
        for version, version_payload in versions.items():
            version_prefix = f'{prefix}.versions.{version}'
            if not isinstance(version_payload, dict):
                errors.append(f'{version_prefix} must be an object')
                continue
            if version_payload.get('installable') is True:
                for field in ['manifest_path', 'bundle_path', 'bundle_sha256', 'attestation_path', 'published_at']:
                    value = version_payload.get(field)
                    if not isinstance(value, str) or not value.strip():
                        errors.append(f'{version_prefix}.{field} must be a non-empty string')
                if not isinstance(version_payload.get('distribution_manifest_path'), str) or not version_payload.get('distribution_manifest_path', '').strip():
                    errors.append(f'{version_prefix}.distribution_manifest_path must be a non-empty string')
                for field in ['manifest_path', 'bundle_path', 'attestation_path']:
                    value = version_payload.get(field)
                    if isinstance(value, str) and value.strip() and not _relative_repo_path(value):
                        errors.append(f'{version_prefix}.{field} must be repo-relative')
                distribution_manifest_path = version_payload.get('distribution_manifest_path')
                if isinstance(distribution_manifest_path, str) and distribution_manifest_path.strip() and not _relative_repo_path(distribution_manifest_path):
                    errors.append(f'{version_prefix}.distribution_manifest_path must be repo-relative')
                signature_path = version_payload.get('attestation_signature_path')
                if signature_path is not None and (
                    not isinstance(signature_path, str) or not signature_path.strip() or not _relative_repo_path(signature_path)
                ):
                    errors.append(f'{version_prefix}.attestation_signature_path must be repo-relative when present')
                if not isinstance(version_payload.get('trust_state'), str) or not version_payload.get('trust_state', '').strip():
                    errors.append(f'{version_prefix}.trust_state must be a non-empty string')
                attestation_formats = version_payload.get('attestation_formats')
                if not isinstance(attestation_formats, list) or not all(isinstance(item, str) for item in attestation_formats):
                    errors.append(f'{version_prefix}.attestation_formats must be an array of strings')
                resolution = version_payload.get('resolution')
                if not isinstance(resolution, dict):
                    errors.append(f'{version_prefix}.resolution must be an object')
                else:
                    if resolution.get('preferred_source') != 'distribution-manifest':
                        errors.append(f'{version_prefix}.resolution.preferred_source must be distribution-manifest')
                    if resolution.get('fallback_allowed') is not False:
                        errors.append(f'{version_prefix}.resolution.fallback_allowed must be false')
    return errors
