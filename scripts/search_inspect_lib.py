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
    return {
        'ok': True,
        'name': skill_entry.get('name'),
        'qualified_name': skill_entry.get('qualified_name'),
        'publisher': skill_entry.get('publisher'),
        'version': resolved_version,
        'latest_version': skill_entry.get('latest_version'),
        'trust_state': version_entry.get('trust_state') or skill_entry.get('trust_state') or 'unknown',
        'compatibility': {
            'declared_support': ((skill_entry.get('compatibility') or {}).get('declared_support') or []),
            'verified_support': ((skill_entry.get('compatibility') or {}).get('verified_support') or {}),
        },
        'dependencies': {
            'root': (distribution.get('dependencies') or {}).get('root') or {},
            'steps': (distribution.get('dependencies') or {}).get('steps') or [],
        },
        'provenance': {
            'attestation_path': version_entry.get('attestation_path') or distribution.get('attestation_path'),
            'attestation_signature_path': version_entry.get('attestation_signature_path') or distribution.get('attestation_signature_path'),
            'attestation_formats': version_entry.get('attestation_formats') or ['ssh'],
        },
        'distribution': {
            'manifest_path': version_entry.get('distribution_manifest_path') or version_entry.get('manifest_path') or distribution.get('manifest_path'),
            'bundle_path': version_entry.get('bundle_path') or distribution.get('bundle_path'),
            'bundle_sha256': version_entry.get('bundle_sha256') or distribution.get('bundle_sha256'),
        },
    }
