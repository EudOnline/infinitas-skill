#!/usr/bin/env python3
import json
from pathlib import Path

from installed_integrity_lib import (
    normalize_integrity_capability_fields,
    normalize_integrity_events,
    normalize_integrity_record,
)
from schema_version_lib import SUPPORTED_SCHEMA_VERSION, validate_schema_version


class InstallManifestError(Exception):
    pass


MANIFEST_FILENAME = '.infinitas-skill-install-manifest.json'


def manifest_path_for(path_or_dir):
    path = Path(path_or_dir)
    if path.name == MANIFEST_FILENAME:
        return path.resolve()
    return (path / MANIFEST_FILENAME).resolve()


def default_install_manifest(repo=None):
    return {
        'schema_version': SUPPORTED_SCHEMA_VERSION,
        'repo': repo,
        'updated_at': None,
        'skills': {},
        'history': {},
    }


def normalize_install_manifest(payload, *, repo=None):
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise InstallManifestError('install manifest must be a JSON object')
    _schema_version, errors = validate_schema_version(payload)
    if errors:
        raise InstallManifestError('; '.join(errors))
    normalized = dict(payload)
    normalized['schema_version'] = SUPPORTED_SCHEMA_VERSION
    if normalized.get('repo') is None:
        normalized['repo'] = repo
    normalized.setdefault('updated_at', None)
    skills = normalized.get('skills')
    if skills is None:
        normalized['skills'] = {}
    elif not isinstance(skills, dict):
        raise InstallManifestError('install manifest skills must be an object')
    else:
        normalized['skills'] = {
            key: _normalize_install_entry(value)
            for key, value in skills.items()
        }
    history = normalized.get('history')
    if history is None:
        normalized['history'] = {}
    elif not isinstance(history, dict):
        raise InstallManifestError('install manifest history must be an object')
    else:
        normalized['history'] = {
            key: [_normalize_install_entry(item) for item in value] if isinstance(value, list) else value
            for key, value in history.items()
        }
    return normalized


def _normalize_install_entry(value):
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    normalized['integrity'] = normalize_integrity_record(value.get('integrity'))
    capability_fields = normalize_integrity_capability_fields(
        value.get('integrity_capability'),
        value.get('integrity_reason'),
    )
    normalized['integrity_capability'] = capability_fields.get('integrity_capability')
    normalized['integrity_reason'] = capability_fields.get('integrity_reason')
    normalized['integrity_events'] = normalize_integrity_events(value.get('integrity_events'))
    last_checked_at = value.get('last_checked_at')
    normalized['last_checked_at'] = last_checked_at if isinstance(last_checked_at, str) and last_checked_at else None
    return normalized


def load_install_manifest(path_or_dir, *, repo=None, allow_missing=False):
    manifest_path = manifest_path_for(path_or_dir)
    if not manifest_path.exists():
        if allow_missing:
            return default_install_manifest(repo=repo)
        raise InstallManifestError(f'missing manifest: {manifest_path}')
    try:
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise InstallManifestError(f'invalid install manifest JSON: {exc}') from exc
    return normalize_install_manifest(payload, repo=repo)


def write_install_manifest(path_or_dir, payload, *, repo=None):
    manifest_path = manifest_path_for(path_or_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_install_manifest(payload, repo=repo)
    manifest_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest_path
