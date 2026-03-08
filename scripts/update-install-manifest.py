#!/usr/bin/env python3
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

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

repo_root = Path(__file__).resolve().parent.parent
try:
    repo_url = subprocess.check_output(
        ['git', '-C', str(repo_root), 'config', '--get', 'remote.origin.url'],
        text=True,
    ).strip()
except Exception:
    repo_url = None

if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
else:
    manifest = {'repo': repo_url, 'updated_at': None, 'skills': {}, 'history': {}}

manifest['repo'] = repo_url or manifest.get('repo')
manifest['updated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
manifest.setdefault('skills', {})
manifest.setdefault('history', {})
name = meta['name']
previous = manifest['skills'].get(name)
if previous:
    hist = manifest['history'].setdefault(name, [])
    hist.append(previous)
    manifest['history'][name] = hist[-25:]

manifest_entry = {
    'name': name,
    'version': meta.get('version'),
    'locked_version': locked_version or meta.get('version'),
    'status': meta.get('status'),
    'source_repo': source_info.get('registry_url') or repo_url,
    'source_registry': source_info.get('registry_name') or 'self',
    'source_registry_kind': source_info.get('registry_kind'),
    'source_trust': source_info.get('registry_trust'),
    'source_ref': source_info.get('registry_ref'),
    'source_commit': source_info.get('registry_commit'),
    'source_tag': source_info.get('registry_tag'),
    'source_expected_tag': source_info.get('expected_tag'),
    'source_resolution_reason': source_info.get('resolution_reason'),
    'source_update_mode': source_info.get('registry_update_mode'),
    'source_pin_mode': source_info.get('registry_pin_mode'),
    'source_pin_value': source_info.get('registry_pin_value'),
    'source_root': source_info.get('registry_root'),
    'source_path': str(source_dir),
    'source_relative_path': source_info.get('relative_path'),
    'source_stage': source_dir.parent.name,
    'source_version': source_meta.get('version'),
    'source_snapshot_of': source_meta.get('snapshot_of'),
    'source_snapshot_created_at': source_meta.get('snapshot_created_at'),
    'target_path': str(dest_dir.relative_to(target_dir)),
    'action': action,
    'updated_at': manifest['updated_at'],
}
if resolution_plan is not None:
    manifest_entry['resolution_plan'] = resolution_plan
manifest['skills'][name] = manifest_entry
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'updated manifest: {manifest_path}')
