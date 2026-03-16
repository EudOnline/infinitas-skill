#!/usr/bin/env python3
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from registry_refresh_state_lib import load_refresh_state


def registry_snapshots_dir(root: Path, registry_name: str) -> Path:
    return (root / '.cache' / 'registry-snapshots' / registry_name).resolve()


def snapshot_dir(root: Path, registry_name: str, snapshot_id: str) -> Path:
    return (registry_snapshots_dir(root, registry_name) / snapshot_id).resolve()


def snapshot_metadata_path(root: Path, registry_name: str, snapshot_id: str) -> Path:
    return snapshot_dir(root, registry_name, snapshot_id) / 'snapshot.json'


def _load_snapshot_metadata_file(metadata_path: Path):
    try:
        payload = json.loads(metadata_path.read_text(encoding='utf-8'))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _path_for_output(root: Path, value):
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value.strip())
    if not path.is_absolute():
        path = (root / path).resolve()
    else:
        path = path.resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _snapshot_sort_key(item):
    return (item.get('created_at') or '', item.get('snapshot_id') or '')


def summarize_snapshot(root: Path, payload, metadata_path: Path):
    if not isinstance(payload, dict):
        return None
    source_registry = payload.get('source_registry') if isinstance(payload.get('source_registry'), dict) else {}
    refresh_state = payload.get('refresh_state') if isinstance(payload.get('refresh_state'), dict) else {}
    snapshot_id = payload.get('snapshot_id') or metadata_path.parent.name
    return {
        'registry': payload.get('registry') or metadata_path.parent.parent.name,
        'snapshot_id': snapshot_id,
        'created_at': payload.get('created_at'),
        'authoritative': bool(payload.get('authoritative', False)),
        'snapshot_root': _path_for_output(root, payload.get('snapshot_root')) or _path_for_output(root, str(metadata_path.parent / 'registry')),
        'metadata_path': _path_for_output(root, str(metadata_path)),
        'source_commit': source_registry.get('commit') or refresh_state.get('source_commit'),
        'source_ref': source_registry.get('ref') or refresh_state.get('source_ref'),
        'source_tag': source_registry.get('tag') or refresh_state.get('source_tag'),
        'source_trust': source_registry.get('trust'),
        'source_update_mode': source_registry.get('update_mode'),
        'refresh_state': refresh_state or None,
    }


def list_registry_snapshots(root: Path, registry_name: str):
    snapshots_root = registry_snapshots_dir(root, registry_name)
    if not snapshots_root.exists():
        return []

    snapshots = []
    for metadata_path in sorted(snapshots_root.glob('*/snapshot.json')):
        payload = _load_snapshot_metadata_file(metadata_path)
        if payload is None:
            continue
        summary = summarize_snapshot(root, payload, metadata_path)
        if summary is not None:
            snapshots.append(summary)

    snapshots.sort(key=_snapshot_sort_key, reverse=True)
    return snapshots


def snapshot_catalog_summary(root: Path, registry_name: str):
    snapshots = list_registry_snapshots(root, registry_name)
    return {
        'snapshot_count': len(snapshots),
        'latest_snapshot': snapshots[0] if snapshots else None,
        'available_snapshots': snapshots,
    }


def load_snapshot_metadata(root: Path, registry_name: str, snapshot_id: str):
    metadata_path = snapshot_metadata_path(root, registry_name, snapshot_id)
    if not metadata_path.exists():
        return None
    payload = _load_snapshot_metadata_file(metadata_path)
    if payload is None:
        return None
    summary = summarize_snapshot(root, payload, metadata_path)
    if summary is None:
        return None
    return {
        'metadata': payload,
        'summary': summary,
        'metadata_path': metadata_path,
        'snapshot_root': metadata_path.parent / 'registry',
    }


def resolve_snapshot_selector(root: Path, registry_name: str, selector: str):
    choice = (selector or '').strip()
    if not choice:
        raise ValueError('snapshot selector must be a non-empty string')
    if choice == 'latest':
        snapshots = list_registry_snapshots(root, registry_name)
        if not snapshots:
            return None
        choice = snapshots[0].get('snapshot_id')
    if not choice:
        return None
    return load_snapshot_metadata(root, registry_name, choice)


def utc_now_iso(now=None) -> str:
    current = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def default_snapshot_id(*, now=None, source_commit=None):
    timestamp = utc_now_iso(now).replace('-', '').replace(':', '')
    suffix = (source_commit or 'snapshot')[:12]
    return f'{timestamp}-{suffix}'


def _write_snapshot_metadata(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def create_snapshot(root: Path, reg, *, snapshot_id=None, now=None):
    from registry_source_lib import normalized_refresh_policy, normalized_update_policy, registry_identity, resolve_registry_root

    registry_name = reg.get('name')
    if reg.get('kind') != 'git':
        raise ValueError(f"registry '{registry_name}' must be a remote cached git registry")
    if normalized_update_policy(reg).get('mode') == 'local-only':
        raise ValueError(f"registry '{registry_name}' is local-only and cannot produce an external snapshot")

    cache_root = resolve_registry_root(root, reg)
    if cache_root is None or not cache_root.exists():
        raise ValueError(f"registry '{registry_name}' cache root is unavailable; sync it before creating a snapshot")

    refresh_policy = normalized_refresh_policy(reg)
    _, refresh_state = load_refresh_state(root, registry_name)
    if any(refresh_policy.get(key) is not None for key in ['interval_hours', 'max_cache_age_hours', 'stale_policy']) and not refresh_state:
        raise ValueError(f"registry '{registry_name}' is missing refresh state; sync it before creating a snapshot")

    identity = registry_identity(root, reg)
    source_commit = identity.get('registry_commit')
    if not source_commit:
        raise ValueError(f"registry '{registry_name}' cache does not expose a source commit")

    chosen_snapshot_id = snapshot_id or default_snapshot_id(now=now, source_commit=source_commit)
    destination = snapshot_dir(root, registry_name, chosen_snapshot_id)
    if destination.exists():
        raise ValueError(f"snapshot '{chosen_snapshot_id}' already exists for registry '{registry_name}'")

    registry_copy_root = destination / 'registry'
    shutil.copytree(cache_root, registry_copy_root)

    metadata = {
        'registry': registry_name,
        'snapshot_id': chosen_snapshot_id,
        'created_at': utc_now_iso(now),
        'authoritative': False,
        'snapshot_root': str(registry_copy_root.resolve()),
        'source_registry': {
            'name': registry_name,
            'kind': reg.get('kind'),
            'trust': reg.get('trust'),
            'update_mode': identity.get('registry_update_mode'),
            'ref': identity.get('registry_ref'),
            'tag': identity.get('registry_tag'),
            'commit': source_commit,
            'origin_url': identity.get('registry_origin_url'),
        },
        'refresh_state': refresh_state,
    }
    metadata_file = destination / 'snapshot.json'
    _write_snapshot_metadata(metadata_file, metadata)

    summary = summarize_snapshot(root, metadata, metadata_file) or {}
    return {
        'registry': registry_name,
        'snapshot_id': chosen_snapshot_id,
        'snapshot_root': summary.get('snapshot_root'),
        'metadata_path': summary.get('metadata_path'),
        'created_at': metadata.get('created_at'),
        'source_commit': summary.get('source_commit'),
        'source_ref': summary.get('source_ref'),
        'source_tag': summary.get('source_tag'),
        'refresh_state': refresh_state,
        'authoritative': False,
    }
