#!/usr/bin/env python3
import json
from pathlib import Path

DEFAULT_COMPATIBILITY_POLICY = {
    'platform_contracts': {
        'max_age_days': 30,
        'stale_policy': 'fail',
    },
    'verified_support': {
        'stale_after_days': 30,
        'contract_newer_than_evidence_policy': 'stale',
        'missing_policy': 'unknown',
    },
}


def default_compatibility_policy() -> dict:
    return json.loads(json.dumps(DEFAULT_COMPATIBILITY_POLICY))


def validate_compatibility_policy_payload(payload) -> list[str]:
    errors = []
    if not isinstance(payload, dict):
        return ['compatibility policy payload must be an object']

    platform_contracts = payload.get('platform_contracts')
    if not isinstance(platform_contracts, dict):
        errors.append('platform_contracts must be an object')
    else:
        max_age_days = platform_contracts.get('max_age_days')
        if not isinstance(max_age_days, int) or max_age_days < 1:
            errors.append('platform_contracts.max_age_days must be an integer >= 1')
        stale_policy = platform_contracts.get('stale_policy')
        if stale_policy not in {'warn', 'fail'}:
            errors.append("platform_contracts.stale_policy must be 'warn' or 'fail'")

    verified_support = payload.get('verified_support')
    if not isinstance(verified_support, dict):
        errors.append('verified_support must be an object')
    else:
        stale_after_days = verified_support.get('stale_after_days')
        if not isinstance(stale_after_days, int) or stale_after_days < 1:
            errors.append('verified_support.stale_after_days must be an integer >= 1')
        contract_policy = verified_support.get('contract_newer_than_evidence_policy')
        if contract_policy not in {'ignore', 'stale'}:
            errors.append("verified_support.contract_newer_than_evidence_policy must be 'ignore' or 'stale'")
        missing_policy = verified_support.get('missing_policy')
        if missing_policy not in {'unknown'}:
            errors.append("verified_support.missing_policy must be 'unknown'")

    return errors


def load_compatibility_policy(root: Path) -> dict:
    root = Path(root).resolve()
    path = root / 'config' / 'compatibility-policy.json'
    if not path.exists():
        return default_compatibility_policy()

    payload = json.loads(path.read_text(encoding='utf-8'))
    errors = validate_compatibility_policy_payload(payload)
    if errors:
        raise ValueError(f'{path}: ' + '; '.join(errors))
    return payload
