#!/usr/bin/env python3
import copy
import json
from pathlib import Path

SUPPORTED_DOMAINS = {'promotion_policy', 'namespace_policy', 'signing', 'registry_sources', 'team_policy', 'exception_policy'}
LOCAL_OVERRIDE_PATHS = {
    'promotion_policy': Path('policy/promotion-policy.json'),
    'namespace_policy': Path('policy/namespace-policy.json'),
    'signing': Path('config/signing.json'),
    'registry_sources': Path('config/registry-sources.json'),
    'team_policy': Path('policy/team-policy.json'),
    'exception_policy': Path('policy/exception-policy.json'),
}
PACK_KEYS = {'$schema', 'schema_version', 'name', 'description', 'domains'}
SELECTION_KEYS = {'$schema', 'version', 'description', 'compatibility_version', 'active_packs'}


class PolicyPackError(Exception):
    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = [str(item) for item in errors if str(item)]
        super().__init__('; '.join(self.errors))


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _load_json_object(path: Path, missing_label: str):
    if not path.exists():
        raise PolicyPackError([f'missing {missing_label}: {path}'])
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise PolicyPackError([f'invalid JSON in {path}: {exc}']) from exc
    if not isinstance(payload, dict):
        raise PolicyPackError([f'{path} must contain a JSON object'])
    return payload


def _validate_selection(payload):
    errors = []
    unknown = sorted(set(payload) - SELECTION_KEYS)
    if unknown:
        errors.append(f'policy-pack selection has unsupported keys: {", ".join(unknown)}')
    if '$schema' in payload and not _is_nonempty_string(payload.get('$schema')):
        errors.append('policy-pack selection $schema must be a string when present')
    version = payload.get('version')
    if not isinstance(version, int) or version < 1:
        errors.append('policy-pack selection version must be an integer >= 1')
    if 'description' in payload and not isinstance(payload.get('description'), str):
        errors.append('policy-pack selection description must be a string when present')
    if 'compatibility_version' in payload and not _is_nonempty_string(payload.get('compatibility_version')):
        errors.append('policy-pack selection compatibility_version must be a non-empty string when present')
    active_packs = payload.get('active_packs')
    if not isinstance(active_packs, list) or not active_packs:
        errors.append('policy-pack selection active_packs must be a non-empty array')
        return errors, []
    clean_names = []
    duplicates = []
    seen = set()
    for item in active_packs:
        if not _is_nonempty_string(item):
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


def _validate_pack(payload, expected_name):
    errors = []
    unknown = sorted(set(payload) - PACK_KEYS)
    if unknown:
        errors.append(f'policy pack {expected_name!r} has unsupported keys: {", ".join(unknown)}')
    if '$schema' in payload and not _is_nonempty_string(payload.get('$schema')):
        errors.append(f'policy pack {expected_name!r} $schema must be a string when present')
    schema_version = payload.get('schema_version')
    if not isinstance(schema_version, int) or schema_version < 1:
        errors.append(f'policy pack {expected_name!r} schema_version must be an integer >= 1')
    name = payload.get('name')
    if not _is_nonempty_string(name):
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


def _merge_values(base, overlay):
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = {key: copy.deepcopy(value) for key, value in base.items()}
        for key, value in overlay.items():
            if key in result:
                result[key] = _merge_values(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result
    return copy.deepcopy(overlay)


def _merge_exception_lists(base, overlay):
    base_items = base if isinstance(base, list) else []
    overlay_items = overlay if isinstance(overlay, list) else []

    ordered_ids = []
    merged = {}
    extras = []
    for source in [base_items, overlay_items]:
        for item in source:
            if isinstance(item, dict):
                raw_id = item.get('id')
                if isinstance(raw_id, str) and raw_id.strip():
                    record_id = raw_id.strip()
                    if record_id not in ordered_ids:
                        ordered_ids.append(record_id)
                        merged[record_id] = copy.deepcopy(item)
                    else:
                        merged[record_id] = _merge_values(merged[record_id], item)
                    continue
            extras.append(copy.deepcopy(item))

    result = [merged[record_id] for record_id in ordered_ids]
    result.extend(extras)
    return result


def _merge_domain_payload(domain, base, overlay):
    merged = _merge_values(base, overlay)
    if domain != 'exception_policy':
        return merged

    base_exceptions = base.get('exceptions') if isinstance(base, dict) else None
    overlay_exceptions = overlay.get('exceptions') if isinstance(overlay, dict) else None
    if base_exceptions is None and overlay_exceptions is None:
        return merged
    merged['exceptions'] = _merge_exception_lists(base_exceptions, overlay_exceptions)
    return merged


def load_policy_pack_selection(root: Path) -> dict:
    root = Path(root).resolve()
    path = root / 'policy' / 'policy-packs.json'
    if not path.exists():
        return {
            'version': 1,
            'active_packs': [],
        }
    payload = _load_json_object(path, 'policy-pack selection file')
    errors, active_packs = _validate_selection(payload)
    if errors:
        raise PolicyPackError(errors)
    return {
        **payload,
        'active_packs': active_packs,
    }


def load_policy_pack(root: Path, name: str) -> dict:
    root = Path(root).resolve()
    pack_path = root / 'policy' / 'packs' / f'{name}.json'
    payload = _load_json_object(pack_path, 'policy pack file')
    errors = _validate_pack(payload, name)
    if errors:
        raise PolicyPackError(errors)
    return payload


def load_policy_domain_resolution(root: Path, domain: str) -> dict:
    root = Path(root).resolve()
    if domain not in SUPPORTED_DOMAINS:
        raise PolicyPackError([f'unsupported policy domain: {domain!r}'])

    effective = {}
    saw_source = False
    effective_sources = []
    selection = load_policy_pack_selection(root)
    for name in selection.get('active_packs', []):
        pack = load_policy_pack(root, name)
        domains = pack.get('domains') or {}
        if domain not in domains:
            continue
        saw_source = True
        effective = _merge_domain_payload(domain, effective, domains.get(domain) or {})
        effective_sources.append(
            {
                'kind': 'pack',
                'name': name,
                'path': f'policy/packs/{name}.json',
            }
        )

    local_path = root / LOCAL_OVERRIDE_PATHS[domain]
    if local_path.exists():
        saw_source = True
        local_payload = _load_json_object(local_path, f'{domain} override file')
        effective = _merge_domain_payload(domain, effective, local_payload)
        effective_sources.append(
            {
                'kind': 'local_override',
                'name': local_path.name,
                'path': str(local_path.relative_to(root).as_posix()),
            }
        )

    if not saw_source:
        raise PolicyPackError([f'missing policy source for domain {domain!r}: expected {local_path} or an active pack entry'])
    return {
        'domain': domain,
        'effective': effective,
        'effective_sources': effective_sources,
    }


def load_effective_policy_domain(root: Path, domain: str) -> dict:
    return load_policy_domain_resolution(root, domain)['effective']
