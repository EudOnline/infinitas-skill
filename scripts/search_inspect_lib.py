#!/usr/bin/env python3
import json
from pathlib import Path


def _load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def _load_ai_index(root: Path):
    return _load_json(root / 'catalog' / 'ai-index.json')


def _load_discovery_index(root: Path):
    return _load_json(root / 'catalog' / 'discovery-index.json')


def _load_distributions(root: Path):
    return _load_json(root / 'catalog' / 'distributions.json')


def _distribution_lookup(root: Path):
    payload = _load_distributions(root)
    lookup = {}
    for item in payload.get('skills') or []:
        if not isinstance(item, dict):
            continue
        lookup[(item.get('qualified_name') or item.get('name'), item.get('version'))] = item
    return lookup


def _load_optional_json(root: Path, relative_path: str | None):
    if not isinstance(relative_path, str) or not relative_path.strip():
        return {}
    path = root / relative_path
    if not path.exists():
        return {}
    try:
        return _load_json(path)
    except Exception:
        return {}


def _compatibility_summary(verified_support: dict) -> dict:
    summary = {}
    for platform, payload in (verified_support or {}).items():
        if not isinstance(platform, str) or not platform.strip():
            continue
        if isinstance(payload, dict) and isinstance(payload.get('state'), str) and payload.get('state').strip():
            summary[platform] = payload.get('state')
    return summary


def _dependency_summary(dependencies: dict) -> dict:
    root = dependencies.get('root') if isinstance(dependencies, dict) else {}
    steps = dependencies.get('steps') if isinstance(dependencies, dict) else []
    registries = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        registry = step.get('registry')
        if isinstance(registry, str) and registry not in registries:
            registries.append(registry)
    return {
        'root_name': (root or {}).get('name'),
        'root_source_type': (root or {}).get('source_type'),
        'step_count': len(steps or []),
        'registries_consulted': registries or list((dependencies.get('registries_consulted') or [])),
    }


def _derive_trust_state(version_entry: dict, manifest_payload: dict, provenance_payload: dict, distribution: dict) -> str:
    signature_present = bool(
        version_entry.get('attestation_signature_path')
        or ((manifest_payload.get('attestation_bundle') or {}).get('signature_path'))
    )
    attestation_present = bool(
        version_entry.get('attestation_path')
        or ((manifest_payload.get('attestation_bundle') or {}).get('provenance_path'))
    )
    policy = (provenance_payload.get('attestation') or {}) if isinstance(provenance_payload, dict) else {}
    if signature_present and policy.get('require_verified_attestation_for_distribution') is not False:
        return 'verified'
    if attestation_present:
        return 'attested'
    if distribution.get('manifest_path') or version_entry.get('distribution_manifest_path') or version_entry.get('manifest_path'):
        return 'installable'
    return version_entry.get('trust_state') or 'unknown'


def search_skills(root: Path, query: str | None = None, publisher: str | None = None, agent: str | None = None, tag: str | None = None) -> dict:
    root = Path(root).resolve()
    payload = _load_discovery_index(root)
    lowered_query = (query or '').strip().lower()
    results = []
    for item in payload.get('skills') or []:
        if not isinstance(item, dict):
            continue
        if lowered_query:
            haystacks = [item.get('name') or '', item.get('qualified_name') or '']
            haystacks.extend(item.get('match_names') or [])
            if not any(lowered_query in value.lower() for value in haystacks if isinstance(value, str)):
                continue
        if publisher and item.get('publisher') != publisher:
            continue
        if agent and agent not in (item.get('agent_compatible') or []):
            continue
        if tag and tag not in (item.get('tags') or []):
            continue
        results.append(
            {
                'name': item.get('name'),
                'qualified_name': item.get('qualified_name'),
                'publisher': item.get('publisher'),
                'summary': item.get('summary'),
                'latest_version': item.get('latest_version'),
                'trust_state': item.get('trust_state'),
                'verified_support': item.get('verified_support') or {},
                'agent_compatible': item.get('agent_compatible') or [],
                'tags': item.get('tags') or [],
                'attestation_formats': item.get('attestation_formats') or [],
                'source_registry': item.get('source_registry'),
            }
        )
    return {
        'ok': True,
        'query': query,
        'publisher': publisher,
        'agent': agent,
        'tag': tag,
        'results': results,
    }


def inspect_skill(root: Path, name: str, version: str | None = None) -> dict:
    root = Path(root).resolve()
    ai_index = _load_ai_index(root)
    distributions = _distribution_lookup(root)
    skill_entry = None
    for item in ai_index.get('skills') or []:
        if not isinstance(item, dict):
            continue
        if name in {item.get('qualified_name'), item.get('name')}:
            skill_entry = item
            break
    if skill_entry is None:
        raise ValueError(f'could not resolve skill {name!r}')

    resolved_version = version or skill_entry.get('latest_version') or skill_entry.get('default_install_version')
    version_entry = ((skill_entry.get('versions') or {}).get(resolved_version) or {})
    distribution = distributions.get((skill_entry.get('qualified_name') or skill_entry.get('name'), resolved_version), {})
    manifest_path = version_entry.get('distribution_manifest_path') or version_entry.get('manifest_path') or distribution.get('manifest_path')
    provenance_path = version_entry.get('attestation_path') or distribution.get('attestation_path')
    manifest_payload = _load_optional_json(root, manifest_path)
    provenance_payload = _load_optional_json(root, provenance_path)
    verified_support = ((skill_entry.get('compatibility') or {}).get('verified_support') or {})
    dependency_view = {
        'root': (manifest_payload.get('dependencies') or {}).get('root') or (distribution.get('dependencies') or {}).get('root') or {},
        'steps': (manifest_payload.get('dependencies') or {}).get('steps') or (distribution.get('dependencies') or {}).get('steps') or [],
    }
    dependency_view['summary'] = _dependency_summary(
        {
            'root': dependency_view.get('root'),
            'steps': dependency_view.get('steps'),
            'registries_consulted': (manifest_payload.get('dependencies') or {}).get('registries_consulted')
            or (distribution.get('dependencies') or {}).get('registries_consulted')
            or [],
        }
    )
    required_formats = version_entry.get('attestation_formats') or [
        ((provenance_payload.get('attestation') or {}).get('format') or 'ssh')
    ]
    trust_state = _derive_trust_state(version_entry, manifest_payload, provenance_payload, distribution)
    return {
        'ok': True,
        'name': skill_entry.get('name'),
        'qualified_name': skill_entry.get('qualified_name'),
        'publisher': skill_entry.get('publisher'),
        'version': resolved_version,
        'latest_version': skill_entry.get('latest_version'),
        'trust_state': trust_state,
        'compatibility': {
            'declared_support': ((skill_entry.get('compatibility') or {}).get('declared_support') or []),
            'verified_support': verified_support,
            'verified_summary': _compatibility_summary(verified_support),
        },
        'dependencies': dependency_view,
        'provenance': {
            'attestation_path': provenance_path,
            'release_provenance_path': provenance_path,
            'attestation_signature_path': version_entry.get('attestation_signature_path') or distribution.get('attestation_signature_path'),
            'attestation_formats': required_formats,
            'required_attestation_formats': required_formats,
            'signer_identity': ((manifest_payload.get('attestation_bundle') or {}).get('signer_identity'))
            or ((provenance_payload.get('attestation') or {}).get('signer_identity')),
            'policy': {
                'policy_mode': ((provenance_payload.get('attestation') or {}).get('policy_mode')),
                'require_verified_attestation_for_release_output': (
                    (provenance_payload.get('attestation') or {}).get('require_verified_attestation_for_release_output')
                ),
                'require_verified_attestation_for_distribution': (
                    (provenance_payload.get('attestation') or {}).get('require_verified_attestation_for_distribution')
                ),
            },
        },
        'distribution': {
            'manifest_path': manifest_path,
            'bundle_path': version_entry.get('bundle_path') or distribution.get('bundle_path'),
            'bundle_sha256': version_entry.get('bundle_sha256') or distribution.get('bundle_sha256'),
            'source_type': distribution.get('source_type') or 'distribution-manifest',
            'bundle_size': distribution.get('bundle_size') or ((manifest_payload.get('bundle') or {}).get('size')),
            'bundle_file_count': distribution.get('bundle_file_count') or ((manifest_payload.get('bundle') or {}).get('file_count')),
        },
        'trust': {
            'state': trust_state,
            'manifest_present': bool(manifest_path),
            'attestation_present': bool(provenance_path),
            'signature_present': bool(
                version_entry.get('attestation_signature_path') or ((manifest_payload.get('attestation_bundle') or {}).get('signature_path'))
            ),
            'required_attestation_formats': required_formats,
        },
    }
