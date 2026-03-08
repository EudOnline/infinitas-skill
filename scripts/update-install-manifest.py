#!/usr/bin/env python3
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if len(sys.argv) != 5:
    print('usage: scripts/update-install-manifest.py <target-dir> <source-dir> <dest-dir> <action>', file=sys.stderr)
    raise SystemExit(1)

target_dir = Path(sys.argv[1]).resolve()
source_dir = Path(sys.argv[2]).resolve()
dest_dir = Path(sys.argv[3]).resolve()
action = sys.argv[4]
manifest_path = target_dir / '.infinitas-skill-install-manifest.json'
meta_path = dest_dir / '_meta.json'

with open(meta_path, 'r', encoding='utf-8') as f:
    meta = json.load(f)

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
    manifest = {'repo': repo_url, 'updated_at': None, 'skills': {}}

manifest['repo'] = repo_url or manifest.get('repo')
manifest['updated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
manifest.setdefault('skills', {})
manifest['skills'][meta['name']] = {
    'name': meta['name'],
    'version': meta.get('version'),
    'status': meta.get('status'),
    'source_repo': repo_url,
    'source_path': str(source_dir.relative_to(repo_root)),
    'target_path': str(dest_dir.relative_to(target_dir)),
    'source_stage': source_dir.parent.name,
    'action': action,
    'updated_at': manifest['updated_at'],
}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'updated manifest: {manifest_path}')
