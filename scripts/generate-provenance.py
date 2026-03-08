#!/usr/bin/env python3
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if len(sys.argv) != 2:
    print('usage: scripts/generate-provenance.py <skill-dir>', file=sys.stderr)
    raise SystemExit(1)

skill_dir = Path(sys.argv[1]).resolve()
root = Path(__file__).resolve().parent.parent
meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))

def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()

try:
    repo_url = git('config', '--get', 'remote.origin.url')
except Exception:
    repo_url = None
try:
    commit = git('rev-parse', 'HEAD')
except Exception:
    commit = None
try:
    branch = git('branch', '--show-current')
except Exception:
    branch = None

tag = f"skill/{meta['name']}/v{meta['version']}"
out = {
    'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'skill': {
        'name': meta.get('name'),
        'version': meta.get('version'),
        'status': meta.get('status'),
        'path': str(skill_dir.relative_to(root)),
        'derived_from': meta.get('derived_from'),
        'snapshot_of': meta.get('snapshot_of'),
    },
    'git': {
        'repo_url': repo_url,
        'branch': branch,
        'commit': commit,
        'expected_tag': tag,
    },
    'registry': {
        'default_registry': json.loads((root / 'config' / 'registry-sources.json').read_text(encoding='utf-8')).get('default_registry')
    }
}
print(json.dumps(out, ensure_ascii=False, indent=2))
