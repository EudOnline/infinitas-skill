#!/usr/bin/env python3
import json
from pathlib import Path

from release_lib import ROOT
from schema_version_lib import SUPPORTED_SCHEMA_VERSION, validate_schema_version


class InstallIntegrityPolicyError(Exception):
    pass


POLICY_PATH = Path('config/install-integrity-policy.json')
DEFAULT_STALE_AFTER_HOURS = 168
DEFAULT_STALE_POLICY = 'warn'
DEFAULT_NEVER_VERIFIED_POLICY = 'warn'
DEFAULT_MAX_INLINE_EVENTS = 20


def default_install_integrity_policy():
    return {
        '$schema': '../schemas/install-integrity-policy.schema.json',
        'schema_version': SUPPORTED_SCHEMA_VERSION,
        'freshness': {
            'stale_after_hours': DEFAULT_STALE_AFTER_HOURS,
            'stale_policy': DEFAULT_STALE_POLICY,
            'never_verified_policy': DEFAULT_NEVER_VERIFIED_POLICY,
        },
        'history': {
            'max_inline_events': DEFAULT_MAX_INLINE_EVENTS,
        },
    }


def normalize_install_integrity_policy(payload):
    base = default_install_integrity_policy()
    if payload is None:
        return base
    if not isinstance(payload, dict):
        raise InstallIntegrityPolicyError('install-integrity policy must be a JSON object')

    _schema_version, errors = validate_schema_version(payload)
    if errors:
        raise InstallIntegrityPolicyError('; '.join(errors))

    normalized = dict(base)
    schema_ref = payload.get('$schema')
    if '$schema' in payload:
        if not isinstance(schema_ref, str) or not schema_ref.strip():
            raise InstallIntegrityPolicyError('install-integrity policy $schema must be a non-empty string when present')
        normalized['$schema'] = schema_ref

    freshness = payload.get('freshness')
    if freshness is None or not isinstance(freshness, dict):
        raise InstallIntegrityPolicyError('install-integrity policy freshness must be an object')
    stale_after_hours = freshness.get('stale_after_hours')
    if not isinstance(stale_after_hours, int) or stale_after_hours < 1:
        raise InstallIntegrityPolicyError('install-integrity policy freshness.stale_after_hours must be an integer >= 1')
    stale_policy = freshness.get('stale_policy', DEFAULT_STALE_POLICY)
    if stale_policy not in {'ignore', 'warn', 'fail'}:
        raise InstallIntegrityPolicyError("install-integrity policy freshness.stale_policy must be one of 'ignore', 'warn', or 'fail'")
    never_verified_policy = freshness.get('never_verified_policy', DEFAULT_NEVER_VERIFIED_POLICY)
    if never_verified_policy not in {'ignore', 'warn', 'fail'}:
        raise InstallIntegrityPolicyError(
            "install-integrity policy freshness.never_verified_policy must be one of 'ignore', 'warn', or 'fail'"
        )
    normalized['freshness'] = {
        'stale_after_hours': stale_after_hours,
        'stale_policy': stale_policy,
        'never_verified_policy': never_verified_policy,
    }

    history = payload.get('history')
    if history is None or not isinstance(history, dict):
        raise InstallIntegrityPolicyError('install-integrity policy history must be an object')
    max_inline_events = history.get('max_inline_events')
    if not isinstance(max_inline_events, int) or max_inline_events < 1:
        raise InstallIntegrityPolicyError('install-integrity policy history.max_inline_events must be an integer >= 1')
    normalized['history'] = {
        'max_inline_events': max_inline_events,
    }
    return normalized


def load_install_integrity_policy(root=ROOT):
    root = Path(root or ROOT).resolve()
    path = (root / POLICY_PATH).resolve()
    if not path.exists():
        return default_install_integrity_policy()
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise InstallIntegrityPolicyError(f'invalid install-integrity policy JSON: {exc}') from exc
    return normalize_install_integrity_policy(payload)
