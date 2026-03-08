#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT
mkdir -p "$ROOT/catalog"

python3 - <<'PY'
import json, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(os.environ['ROOT'])
skills_root = root / 'skills'
out_catalog = root / 'catalog' / 'catalog.json'
out_active = root / 'catalog' / 'active.json'

entries = []
for stage in ['incubating', 'active', 'archived']:
    stage_dir = skills_root / stage
    if not stage_dir.exists():
        continue
    for skill_dir in sorted(p for p in stage_dir.iterdir() if p.is_dir()):
        meta_path = skill_dir / '_meta.json'
        skill_md = skill_dir / 'SKILL.md'
        if not meta_path.exists() or not skill_md.exists():
            continue
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        entry = {
            'name': meta.get('name', skill_dir.name),
            'version': meta.get('version'),
            'status': meta.get('status', stage),
            'summary': meta.get('summary', ''),
            'owner': meta.get('owner'),
            'maintainers': meta.get('maintainers', []),
            'tags': meta.get('tags', []),
            'review_state': meta.get('review_state'),
            'risk_level': meta.get('risk_level'),
            'derived_from': meta.get('derived_from'),
            'agent_compatible': meta.get('agent_compatible', []),
            'installable': bool(meta.get('distribution', {}).get('installable', True)),
            'path': str(skill_dir.relative_to(root)),
        }
        entries.append(entry)

catalog = {
    'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'count': len(entries),
    'skills': entries,
}
active = {
    'generated_at': catalog['generated_at'],
    'count': sum(1 for e in entries if e['status'] == 'active' and e['installable']),
    'skills': [e for e in entries if e['status'] == 'active' and e['installable']],
}

def normalized(payload):
    clone = dict(payload)
    clone.pop('generated_at', None)
    return json.dumps(clone, ensure_ascii=False, sort_keys=True)

def write_if_changed(path, payload):
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf-8'))
        if normalized(existing) == normalized(payload):
            print(f'unchanged: {path}')
            return
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'wrote: {path}')

write_if_changed(out_catalog, catalog)
write_if_changed(out_active, active)
PY
