#!/usr/bin/env python3
from pathlib import Path

from distribution_lib import (
    DistributionError,
    installed_integrity_capability_summary,
    load_json,
    sha256_file,
    verify_distribution_manifest,
)
from release_lib import ROOT


class InstalledIntegrityError(Exception):
    pass


class MissingSignedFileManifestError(InstalledIntegrityError):
    pass


def default_integrity_record():
    return {
        'state': 'unknown',
        'last_verified_at': None,
        'checked_file_count': 0,
        'release_file_manifest_count': 0,
        'modified_count': 0,
        'missing_count': 0,
        'unexpected_count': 0,
        'modified_files': [],
        'missing_files': [],
        'unexpected_files': [],
    }


def default_integrity_capability_fields():
    return {
        'integrity_capability': 'unknown',
        'integrity_reason': None,
    }


def default_integrity_events():
    return []


def normalize_integrity_record(record):
    normalized = default_integrity_record()
    if not isinstance(record, dict):
        return normalized

    state = record.get('state')
    if state in {'unknown', 'verified', 'drifted'}:
        normalized['state'] = state

    last_verified_at = record.get('last_verified_at')
    if isinstance(last_verified_at, str) and last_verified_at:
        normalized['last_verified_at'] = last_verified_at

    for key in [
        'checked_file_count',
        'release_file_manifest_count',
        'modified_count',
        'missing_count',
        'unexpected_count',
    ]:
        value = record.get(key)
        if isinstance(value, int) and value >= 0:
            normalized[key] = value

    for key in ['modified_files', 'missing_files', 'unexpected_files']:
        value = record.get(key)
        if isinstance(value, list):
            normalized[key] = [item for item in value if isinstance(item, str) and item]

    return normalized


def normalize_integrity_capability_fields(capability=None, reason=None):
    normalized = default_integrity_capability_fields()
    if capability == 'supported':
        normalized['integrity_capability'] = 'supported'
        normalized['integrity_reason'] = None
        return normalized
    if isinstance(reason, str) and reason:
        normalized['integrity_reason'] = reason
    return normalized


def normalize_integrity_event(event):
    if not isinstance(event, dict):
        return None
    normalized = {}
    for key in ['at', 'event', 'source']:
        value = event.get(key)
        if not isinstance(value, str) or not value:
            return None
        normalized[key] = value
    reason = event.get('reason')
    if isinstance(reason, str) and reason:
        normalized['reason'] = reason
    return normalized


def normalize_integrity_events(events):
    if not isinstance(events, list):
        return default_integrity_events()
    normalized = []
    for item in events:
        event = normalize_integrity_event(item)
        if event is not None:
            normalized.append(event)
    return normalized


def append_integrity_event(events, *, at, event, source, reason=None):
    normalized = normalize_integrity_events(events)
    payload = {
        'at': at,
        'event': event,
        'source': source,
    }
    if isinstance(reason, str) and reason:
        payload['reason'] = reason
    normalized_event = normalize_integrity_event(payload)
    if normalized_event is None:
        raise InstalledIntegrityError('integrity event payload is invalid')
    normalized.append(normalized_event)
    return normalized


def _relative_path(path: Path, root: Path):
    return path.relative_to(root).as_posix()


def _actual_file_manifest(installed_dir: Path):
    manifest = {}
    for path in sorted(installed_dir.rglob('*')):
        if not path.is_file():
            continue
        manifest[_relative_path(path, installed_dir)] = sha256_file(path)
    return manifest


def _expected_file_manifest(entries):
    if not isinstance(entries, list) or not entries:
        raise MissingSignedFileManifestError('distribution manifest is missing signed file_manifest entries')

    manifest = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise InstalledIntegrityError('distribution manifest file_manifest entries must be objects')
        rel_path = entry.get('path')
        digest = entry.get('sha256')
        if not isinstance(rel_path, str) or not rel_path:
            raise InstalledIntegrityError('distribution manifest file_manifest entry is missing path')
        if not isinstance(digest, str) or not digest:
            raise InstalledIntegrityError(f'distribution manifest file_manifest entry {rel_path!r} is missing sha256')
        manifest[rel_path] = digest
    return manifest


def _resolve_distribution_manifest_path(manifest_ref: str, *, distribution_root: Path, root: Path):
    manifest_path = Path(manifest_ref)
    if manifest_path.is_absolute():
        return manifest_path.resolve()
    root_candidate = (distribution_root / manifest_path).resolve()
    if root_candidate.exists():
        return root_candidate
    return (root / manifest_path).resolve()


def installed_integrity_capability_for_source(source_info, *, root=None):
    root = Path(root or ROOT).resolve()
    source_info = source_info or {}
    manifest_ref = source_info.get('distribution_manifest') or source_info.get('source_distribution_manifest')
    if not isinstance(manifest_ref, str) or not manifest_ref:
        return default_integrity_capability_fields()

    distribution_root = Path(source_info.get('distribution_root') or source_info.get('source_distribution_root') or root).resolve()
    try:
        manifest_path = _resolve_distribution_manifest_path(
            manifest_ref,
            distribution_root=distribution_root,
            root=root,
        )
        payload = load_json(manifest_path)
    except Exception:
        return default_integrity_capability_fields()

    summary = installed_integrity_capability_summary(payload)
    return normalize_integrity_capability_fields(
        summary.get('installed_integrity_capability'),
        summary.get('installed_integrity_reason'),
    )


def _verify_installed_dir(installed_dir: Path, manifest_ref: str, *, root: Path, distribution_root: Path | None = None, item=None):
    distribution_root = Path(distribution_root or root).resolve()
    try:
        verified_distribution = verify_distribution_manifest(manifest_ref, root=distribution_root, attestation_root=root)
    except DistributionError as exc:
        raise InstalledIntegrityError(str(exc)) from exc

    expected_files = _expected_file_manifest((verified_distribution.get('manifest') or {}).get('file_manifest'))
    actual_files = _actual_file_manifest(installed_dir)

    modified_files = sorted(path for path, digest in expected_files.items() if path in actual_files and actual_files[path] != digest)
    missing_files = sorted(path for path in expected_files if path not in actual_files)
    unexpected_files = sorted(path for path in actual_files if path not in expected_files)
    state = 'verified' if not modified_files and not missing_files and not unexpected_files else 'drifted'

    payload = {
        'state': state,
        'release_file_manifest_count': len(expected_files),
        'checked_file_count': len(expected_files),
        'actual_file_count': len(actual_files),
        'modified_files': modified_files,
        'missing_files': missing_files,
        'unexpected_files': unexpected_files,
        'modified_count': len(modified_files),
        'missing_count': len(missing_files),
        'unexpected_count': len(unexpected_files),
    }
    if item is not None:
        recorded_integrity = normalize_integrity_record(item.get('integrity'))
        payload.update(
            {
                'qualified_name': item.get('source_qualified_name') or item.get('qualified_name') or item.get('name'),
                'installed_name': item.get('name'),
                'installed_version': item.get('installed_version') or item.get('version'),
                'installed_path': str(installed_dir),
                'source_registry': item.get('source_registry') or 'self',
                'source_distribution_manifest': manifest_ref,
                'source_attestation_path': item.get('source_attestation_path'),
                'last_verified_at': recorded_integrity.get('last_verified_at'),
            }
        )
    return payload


def build_install_integrity_snapshot(installed_dir, source_info, *, root=None, verified_at=None):
    root = Path(root or ROOT).resolve()
    installed_dir = Path(installed_dir).resolve()
    source_info = source_info or {}
    capability = installed_integrity_capability_for_source(source_info, root=root)

    manifest_ref = source_info.get('distribution_manifest') or source_info.get('source_distribution_manifest')
    distribution_root = source_info.get('distribution_root') or source_info.get('source_distribution_root')
    attestation_ref = source_info.get('distribution_attestation') or source_info.get('source_attestation_path')
    if not isinstance(manifest_ref, str) or not manifest_ref or not isinstance(attestation_ref, str) or not attestation_ref:
        return {
            'integrity': normalize_integrity_record({'state': 'unknown'}),
            **capability,
        }

    try:
        payload = _verify_installed_dir(installed_dir, manifest_ref, root=root, distribution_root=distribution_root)
    except MissingSignedFileManifestError:
        return {
            'integrity': normalize_integrity_record({'state': 'unknown'}),
            **capability,
        }

    payload['last_verified_at'] = verified_at
    return {
        'integrity': normalize_integrity_record(payload),
        **capability,
    }


def build_install_integrity_record(installed_dir, source_info, *, root=None, verified_at=None):
    snapshot = build_install_integrity_snapshot(
        installed_dir,
        source_info,
        root=root,
        verified_at=verified_at,
    )
    return snapshot['integrity']


def recommended_action_for_integrity(integrity_record, *, capability='unknown', reason=None):
    integrity = normalize_integrity_record(integrity_record)
    state = integrity.get('state')
    if state == 'verified':
        return 'none'
    if state == 'drifted':
        return 'repair'
    if capability == 'unknown' and reason == 'missing-signed-file-manifest':
        return 'backfill-distribution-manifest'
    return 'reinstall'


def build_installed_integrity_report_item(name, item):
    item = item or {}
    integrity = normalize_integrity_record(item.get('integrity'))
    capability_fields = normalize_integrity_capability_fields(
        item.get('integrity_capability'),
        item.get('integrity_reason'),
    )
    events = normalize_integrity_events(item.get('integrity_events'))
    return {
        'name': item.get('name') or name,
        'qualified_name': item.get('source_qualified_name') or item.get('qualified_name') or item.get('name') or name,
        'installed_version': item.get('installed_version') or item.get('version'),
        'integrity': integrity,
        'integrity_capability': capability_fields.get('integrity_capability'),
        'integrity_reason': capability_fields.get('integrity_reason'),
        'last_verified_at': integrity.get('last_verified_at'),
        'recommended_action': recommended_action_for_integrity(
            integrity,
            capability=capability_fields.get('integrity_capability'),
            reason=capability_fields.get('integrity_reason'),
        ),
        'integrity_events': events,
    }


def verify_installed_skill(target_dir, requested_name, *, root=None):
    from installed_skill_lib import InstalledSkillError, load_installed_skill

    root = Path(root or ROOT).resolve()
    target_dir = Path(target_dir).resolve()

    try:
        _manifest, item = load_installed_skill(target_dir, requested_name)
    except InstalledSkillError as exc:
        raise InstalledIntegrityError(str(exc)) from exc

    installed_name = item.get('name') or requested_name
    installed_dir = target_dir / installed_name
    if not installed_dir.is_dir():
        raise InstalledIntegrityError(f'installed skill directory is missing: {installed_dir}')

    manifest_ref = item.get('source_distribution_manifest')
    distribution_root = item.get('source_distribution_root')
    attestation_ref = item.get('source_attestation_path')
    if not isinstance(manifest_ref, str) or not manifest_ref:
        raise InstalledIntegrityError('installed skill is missing source_distribution_manifest')
    if not isinstance(attestation_ref, str) or not attestation_ref:
        raise InstalledIntegrityError('installed skill is missing source_attestation_path')
    payload = _verify_installed_dir(
        installed_dir,
        manifest_ref,
        root=root,
        distribution_root=distribution_root,
        item=item,
    )
    payload['installed_name'] = installed_name
    return payload
