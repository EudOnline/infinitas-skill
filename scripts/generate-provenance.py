#!/usr/bin/env python3
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from release_lib import ROOT, collect_release_state, resolve_skill, ReleaseError

if len(sys.argv) != 2:
    print('usage: scripts/generate-provenance.py <skill-dir>', file=sys.stderr)
    raise SystemExit(1)

try:
    skill_dir = resolve_skill(ROOT, sys.argv[1])
    state = collect_release_state(skill_dir, mode='stable-release')
except ReleaseError as exc:
    print(f'FAIL: {exc}', file=sys.stderr)
    raise SystemExit(1)

if not state['release_ready']:
    for error in state['errors']:
        print(f'FAIL: {error}', file=sys.stderr)
    raise SystemExit(1)

meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
default_registry = json.loads((ROOT / 'config' / 'registry-sources.json').read_text(encoding='utf-8')).get('default_registry')
remote_tag = state['git']['remote_tag']
local_tag = state['git']['local_tag']
tag_name = state['git']['expected_tag']
commit = remote_tag.get('target_commit') or local_tag.get('target_commit') or state['git']['head_commit']

out = {
    'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'skill': {
        'name': meta.get('name'),
        'version': meta.get('version'),
        'status': meta.get('status'),
        'path': str(skill_dir.relative_to(ROOT)),
        'derived_from': meta.get('derived_from'),
        'snapshot_of': meta.get('snapshot_of'),
    },
    'git': {
        'repo_url': state['git'].get('repo_url'),
        'branch': state['git'].get('branch'),
        'upstream': state['git'].get('upstream'),
        'commit': commit,
        'head_commit': state['git'].get('head_commit'),
        'expected_tag': tag_name,
        'release_ref': f'refs/tags/{tag_name}',
        'remote': remote_tag.get('name'),
        'remote_tag_object': remote_tag.get('tag_object'),
        'remote_tag_commit': remote_tag.get('target_commit'),
        'signed_tag_verified': True,
        'tag_signer': local_tag.get('signer'),
    },
    'source_snapshot': {
        'kind': 'git-tag',
        'tag': tag_name,
        'ref': f'refs/tags/{tag_name}',
        'commit': commit,
        'remote': remote_tag.get('name'),
        'upstream': state['git'].get('upstream'),
        'immutable': True,
        'pushed': True,
    },
    'registry': {
        'default_registry': default_registry,
    },
}
print(json.dumps(out, ensure_ascii=False, indent=2))
