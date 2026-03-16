#!/usr/bin/env python3
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

EXPECTED_SKILLS = {
    'lvxiaoer/operate-infinitas-skill': {
        'evidence_platforms': {'claude', 'codex', 'openclaw'},
    },
    'lvxiaoer/release-infinitas-skill': {
        'evidence_platforms': {'claude', 'codex'},
    },
    'lvxiaoer/consume-infinitas-skill': {
        'evidence_platforms': {'claude', 'codex', 'openclaw'},
    },
    'lvxiaoer/federation-registry-ops': {
        'evidence_platforms': {'claude', 'codex'},
    },
}


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'could not load JSON {path}: {exc}')


def non_empty_string_list(value):
    return isinstance(value, list) and value and all(isinstance(item, str) and item.strip() for item in value)


def main():
    ai_index = load_json(ROOT / 'catalog' / 'ai-index.json')
    discovery_index = load_json(ROOT / 'catalog' / 'discovery-index.json')
    compatibility = load_json(ROOT / 'catalog' / 'compatibility.json')

    ai_entries = {item.get('qualified_name'): item for item in ai_index.get('skills') or [] if isinstance(item, dict)}
    discovery_entries = {
        item.get('qualified_name'): item for item in discovery_index.get('skills') or [] if isinstance(item, dict)
    }
    compatibility_entries = {
        item.get('qualified_name'): item for item in compatibility.get('skills') or [] if isinstance(item, dict)
    }

    for qualified_name, expected in EXPECTED_SKILLS.items():
        ai_entry = ai_entries.get(qualified_name)
        if ai_entry is None:
            fail(f'missing ai-index entry for {qualified_name}')
        discovery_entry = discovery_entries.get(qualified_name)
        if discovery_entry is None:
            fail(f'missing discovery-index entry for {qualified_name}')
        compatibility_entry = compatibility_entries.get(qualified_name)
        if compatibility_entry is None:
            fail(f'missing compatibility entry for {qualified_name}')

        for label, entry in [('ai-index', ai_entry), ('discovery-index', discovery_entry)]:
            for field in ['use_when', 'avoid_when', 'runtime_assumptions', 'capabilities']:
                if not non_empty_string_list(entry.get(field)):
                    fail(f'{label} {qualified_name} missing non-empty {field}')
            if not isinstance(entry.get('maturity'), str) or not entry.get('maturity', '').strip():
                fail(f'{label} {qualified_name} missing maturity')
            if not isinstance(entry.get('quality_score'), int) or entry.get('quality_score') <= 0:
                fail(f'{label} {qualified_name} missing positive quality_score')
            if not isinstance(entry.get('verified_support'), dict) or not entry.get('verified_support'):
                fail(f'{label} {qualified_name} missing verified_support')

        versions = ai_entry.get('versions') or {}
        latest_version = ai_entry.get('latest_version')
        version_entry = versions.get(latest_version) or {}
        for field in ['manifest_path', 'bundle_path', 'attestation_path']:
            rel_path = version_entry.get(field)
            if not isinstance(rel_path, str) or not rel_path.strip():
                fail(f'ai-index {qualified_name} missing version field {field}')
            if not (ROOT / rel_path).exists():
                fail(f'ai-index {qualified_name} missing artifact file {rel_path}')

        verified_support = compatibility_entry.get('verified_support') or {}
        missing_platforms = expected['evidence_platforms'] - set(verified_support.keys())
        if missing_platforms:
            fail(f'compatibility {qualified_name} missing evidence for {sorted(missing_platforms)!r}')

        for platform in expected['evidence_platforms']:
            evidence = verified_support.get(platform) or {}
            evidence_path = evidence.get('evidence_path')
            if not isinstance(evidence_path, str) or not evidence_path.strip():
                fail(f'compatibility {qualified_name} missing evidence_path for {platform}')
            if not (ROOT / evidence_path).exists():
                fail(f'compatibility {qualified_name} missing evidence file {evidence_path}')

    print('OK: real skill inventory checks passed')


if __name__ == '__main__':
    main()
