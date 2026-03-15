#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_DOMAINS = {'promotion_policy', 'namespace_policy', 'signing', 'registry_sources'}
NAME_KEYS = {'$schema', 'schema_version', 'name', 'description', 'domains'}
SELECTOR_KEYS = {'$schema', 'version', 'description', 'compatibility_version', 'active_packs'}


def load_json_object(path: Path):
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ValueError(f'invalid JSON in {path}: {exc}') from exc
    if not isinstance(payload, dict):
        raise ValueError(f'{path} must contain a JSON object')
    return payload


def is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_selector(path: Path, payload):
    errors = []
    unknown = sorted(set(payload) - SELECTOR_KEYS)
    if unknown:
        errors.append(f'policy-pack selection has unsupported keys: {", ".join(unknown)}')
    if '$schema' in payload and not is_nonempty_string(payload.get('$schema')):
        errors.append('policy-pack selection $schema must be a string when present')
    version = payload.get('version')
    if not isinstance(version, int) or version < 1:
        errors.append('policy-pack selection version must be an integer >= 1')
    if 'description' in payload and not isinstance(payload.get('description'), str):
        errors.append('policy-pack selection description must be a string when present')
    if 'compatibility_version' in payload and not is_nonempty_string(payload.get('compatibility_version')):
        errors.append('policy-pack selection compatibility_version must be a non-empty string when present')
    active_packs = payload.get('active_packs')
    if not isinstance(active_packs, list) or not active_packs:
        errors.append('policy-pack selection active_packs must be a non-empty array')
        return errors, []
    clean_names = []
    seen = set()
    duplicates = []
    for item in active_packs:
        if not is_nonempty_string(item):
            errors.append('policy-pack selection active_packs entries must be non-empty strings')
            continue
        name = item.strip()
        clean_names.append(name)
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        errors.append(f'duplicate active pack names: {", ".join(duplicates)}')
    return errors, clean_names


def validate_pack(path: Path, expected_name: str, payload):
    errors = []
    unknown = sorted(set(payload) - NAME_KEYS)
    if unknown:
        errors.append(f'policy pack {expected_name!r} has unsupported keys: {", ".join(unknown)}')
    if '$schema' in payload and not is_nonempty_string(payload.get('$schema')):
        errors.append(f'policy pack {expected_name!r} $schema must be a string when present')
    schema_version = payload.get('schema_version')
    if not isinstance(schema_version, int) or schema_version < 1:
        errors.append(f'policy pack {expected_name!r} schema_version must be an integer >= 1')
    name = payload.get('name')
    if not is_nonempty_string(name):
        errors.append(f'policy pack {expected_name!r} name must be a non-empty string')
    elif name.strip() != expected_name:
        errors.append(f'policy pack {expected_name!r} name must match file stem, got {name!r}')
    if 'description' in payload and not isinstance(payload.get('description'), str):
        errors.append(f'policy pack {expected_name!r} description must be a string when present')
    domains = payload.get('domains')
    if not isinstance(domains, dict) or not domains:
        errors.append(f'policy pack {expected_name!r} domains must be a non-empty object')
        return errors
    for domain_name, domain_payload in domains.items():
        if domain_name not in SUPPORTED_DOMAINS:
            errors.append(f'unknown policy domain {domain_name!r} in pack {expected_name!r}')
            continue
        if not isinstance(domain_payload, dict):
            errors.append(f'policy pack {expected_name!r} domain {domain_name!r} must be an object')
    return errors


def main():
    selector_path = ROOT / 'policy' / 'policy-packs.json'
    try:
        selector = load_json_object(selector_path)
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    errors, active_packs = validate_selector(selector_path, selector)
    for pack_name in active_packs:
        pack_path = ROOT / 'policy' / 'packs' / f'{pack_name}.json'
        if not pack_path.exists():
            errors.append(f'missing policy pack file: {pack_path}')
            continue
        try:
            payload = load_json_object(pack_path)
        except Exception as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_pack(pack_path, pack_name, payload))

    if errors:
        for error in errors:
            print(f'FAIL: {error}', file=sys.stderr)
        raise SystemExit(1)
    print(f'OK: validated {len(active_packs)} policy pack(s)')


if __name__ == '__main__':
    main()
