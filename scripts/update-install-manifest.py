#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from installed_integrity_lib import append_integrity_event, build_install_integrity_snapshot, normalize_integrity_events
from install_manifest_lib import load_install_manifest, write_install_manifest
from skill_identity_lib import normalize_skill_identity


def _persist_distribution_cache(target_dir: Path, source_info):
    source_info = source_info or {}
    if source_info.get('source_type') != 'distribution-manifest' or source_info.get('registry_kind') != 'http':
        return None
    temp_root = source_info.get('cleanup_dir')
    if not isinstance(temp_root, str) or not temp_root:
        return None

    refs = {
        'manifest': source_info.get('distribution_manifest'),
        'bundle': source_info.get('distribution_bundle'),
        'attestation': source_info.get('distribution_attestation'),
        'signature': source_info.get('distribution_attestation_signature'),
    }
    for label, rel in refs.items():
        if not isinstance(rel, str) or not rel:
            raise SystemExit(f'FAIL: hosted source is missing distribution {label} reference for cache persistence')

    source_root = Path(temp_root).resolve()
    skill_id = source_info.get('qualified_name') or source_info.get('name') or 'unknown-skill'
    version = source_info.get('version') or 'unknown-version'
    digest = source_info.get('distribution_bundle_sha256') or 'unknown-digest'
    cache_root = (target_dir / '.infinitas-skill-distributions' / skill_id / version / digest[:16]).resolve()

    for rel in refs.values():
        ref = Path(rel)
        if ref.is_absolute():
            raise SystemExit(f'FAIL: hosted distribution cache reference must be relative, got: {rel}')
        src = (source_root / ref).resolve()
        if not src.is_relative_to(source_root):
            raise SystemExit(f'FAIL: hosted distribution cache reference is unsafe: {rel}')
        if not src.exists():
            raise SystemExit(f'FAIL: hosted distribution cache source is missing: {src}')
        dst = (cache_root / ref).resolve()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    return str(cache_root)

if len(sys.argv) not in {7, 8}:
    print('usage: scripts/update-install-manifest.py <target-dir> <source-dir> <dest-dir> <action> <locked-version> <resolved-source-json> [resolution-plan-json]', file=sys.stderr)
    raise SystemExit(1)

target_dir = Path(sys.argv[1]).resolve()
source_dir = Path(sys.argv[2]).resolve()
dest_dir = Path(sys.argv[3]).resolve()
action = sys.argv[4]
locked_version = sys.argv[5]
source_info = json.loads(sys.argv[6]) if sys.argv[6] else {}
resolution_plan = json.loads(sys.argv[7]) if len(sys.argv) == 8 and sys.argv[7] else None
manifest_path = target_dir / '.infinitas-skill-install-manifest.json'
meta_path = dest_dir / '_meta.json'
source_meta_path = source_dir / '_meta.json'

with open(meta_path, 'r', encoding='utf-8') as f:
    meta = json.load(f)
with open(source_meta_path, 'r', encoding='utf-8') as f:
    source_meta = json.load(f)

identity = normalize_skill_identity(meta)
source_identity = normalize_skill_identity(source_meta)

repo_root = Path(__file__).resolve().parent.parent
try:
    repo_url = subprocess.check_output(
        ['git', '-C', str(repo_root), 'config', '--get', 'remote.origin.url'],
        text=True,
    ).strip()
except Exception:
    repo_url = None

manifest = load_install_manifest(target_dir, repo=repo_url, allow_missing=True)
manifest['repo'] = repo_url or manifest.get('repo')
manifest['updated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
manifest.setdefault('skills', {})
manifest.setdefault('history', {})
name = meta['name']
distribution_cache_root = _persist_distribution_cache(target_dir, source_info)
previous = manifest['skills'].get(name)
previous_events = normalize_integrity_events(previous.get('integrity_events')) if isinstance(previous, dict) else []
if previous:
    hist = manifest['history'].setdefault(name, [])
    hist.append(previous)
    manifest['history'][name] = hist[-25:]

manifest_entry = {
    'name': name,
    'publisher': identity.get('publisher'),
    'qualified_name': identity.get('qualified_name'),
    'identity_mode': identity.get('identity_mode'),
    'author': identity.get('author'),
    'owners': identity.get('owners', []),
    'maintainers': identity.get('maintainers', []),
    'version': meta.get('version'),
    'locked_version': locked_version or meta.get('version'),
    'status': meta.get('status'),
    'source_type': source_info.get('source_type') or 'working-tree',
    'source_repo': source_info.get('registry_url') or repo_url,
    'source_registry': source_info.get('registry_name') or 'self',
    'source_registry_kind': source_info.get('registry_kind'),
    'source_trust': source_info.get('registry_trust'),
    'source_ref': source_info.get('registry_ref'),
    'source_commit': source_info.get('registry_commit'),
    'source_tag': source_info.get('registry_tag'),
    'source_registry_snapshot_id': source_info.get('registry_snapshot_id'),
    'source_registry_snapshot_path': source_info.get('registry_snapshot_path'),
    'source_registry_snapshot_created_at': source_info.get('registry_snapshot_created_at'),
    'source_registry_snapshot_metadata_path': source_info.get('registry_snapshot_metadata_path'),
    'source_expected_tag': source_info.get('expected_tag'),
    'source_resolution_reason': source_info.get('resolution_reason'),
    'source_update_mode': source_info.get('registry_update_mode'),
    'source_pin_mode': source_info.get('registry_pin_mode'),
    'source_pin_value': source_info.get('registry_pin_value'),
    'source_root': source_info.get('registry_root'),
    'source_path': source_info.get('skill_path') or source_info.get('path') or str(source_dir),
    'source_relative_path': source_info.get('relative_path'),
    'source_stage': source_info.get('source_stage') or source_info.get('stage') or source_dir.parent.name,
    'source_publisher': source_identity.get('publisher'),
    'source_qualified_name': source_identity.get('qualified_name'),
    'source_identity_mode': source_identity.get('identity_mode'),
    'source_version': source_meta.get('version'),
    'source_snapshot_of': source_meta.get('snapshot_of'),
    'source_snapshot_created_at': source_meta.get('snapshot_created_at'),
    'source_snapshot_kind': source_info.get('source_snapshot_kind'),
    'source_snapshot_tag': source_info.get('source_snapshot_tag'),
    'source_snapshot_ref': source_info.get('source_snapshot_ref'),
    'source_snapshot_commit': source_info.get('source_snapshot_commit'),
    'source_distribution_manifest': source_info.get('distribution_manifest'),
    'source_distribution_root': distribution_cache_root,
    'source_distribution_bundle': source_info.get('distribution_bundle'),
    'source_distribution_bundle_sha256': source_info.get('distribution_bundle_sha256'),
    'source_distribution_bundle_size': source_info.get('distribution_bundle_size'),
    'source_distribution_bundle_root_dir': source_info.get('distribution_bundle_root_dir'),
    'source_distribution_bundle_file_count': source_info.get('distribution_bundle_file_count'),
    'source_attestation_path': source_info.get('distribution_attestation'),
    'source_attestation_signature_path': source_info.get('distribution_attestation_signature'),
    'source_attestation_sha256': source_info.get('distribution_attestation_sha256'),
    'source_attestation_signature_sha256': source_info.get('distribution_attestation_signature_sha256'),
    'target_path': str(dest_dir.relative_to(target_dir)),
    'install_target': str(target_dir),
    'installed_version': meta.get('version'),
    'resolved_release_digest': source_info.get('distribution_bundle_sha256'),
    'installed_at': manifest['updated_at'],
    'last_checked_at': manifest['updated_at'],
    'target_agent': source_info.get('target_agent'),
    'install_mode': action,
    'action': action,
    'updated_at': manifest['updated_at'],
}
if resolution_plan is not None:
    manifest_entry['resolution_plan'] = resolution_plan
integrity_source_info = dict(source_info or {})
if distribution_cache_root:
    integrity_source_info['distribution_root'] = distribution_cache_root
integrity_snapshot = build_install_integrity_snapshot(
    dest_dir,
    integrity_source_info,
    root=repo_root,
    verified_at=manifest['updated_at'],
)
manifest_entry['integrity'] = integrity_snapshot['integrity']
manifest_entry['integrity_capability'] = integrity_snapshot['integrity_capability']
manifest_entry['integrity_reason'] = integrity_snapshot['integrity_reason']
manifest_entry['integrity_events'] = append_integrity_event(
    previous_events,
    at=manifest['updated_at'],
    event=manifest_entry['integrity'].get('state') or 'unknown',
    source=action,
    reason=manifest_entry.get('integrity_reason'),
)
manifest['skills'][name] = manifest_entry
manifest_path = write_install_manifest(target_dir, manifest, repo=repo_url)
print(f'updated manifest: {manifest_path}')
