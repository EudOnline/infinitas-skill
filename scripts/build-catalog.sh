#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT
mkdir -p "$ROOT/catalog"

python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ['ROOT'])
sys.path.insert(0, str(root / 'scripts'))

from registry_source_lib import load_registry_config, registry_identity, resolve_registry_root  # noqa: E402


def expected_skill_tag(name, version):
    if not name or not version:
        return None
    return f'skill/{name}/v{version}'


cfg = load_registry_config(root)
catalog_source_registry = None
for reg in cfg.get('registries', []):
    if resolve_registry_root(root, reg) == root:
        catalog_source_registry = reg
        break
if catalog_source_registry is None:
    catalog_source_registry = next((reg for reg in cfg.get('registries', []) if reg.get('name') == cfg.get('default_registry')), None)
catalog_source_identity = registry_identity(root, catalog_source_registry) if catalog_source_registry else {}

skills_root = root / 'skills'
out_catalog = root / 'catalog' / 'catalog.json'
out_active = root / 'catalog' / 'active.json'
out_compat = root / 'catalog' / 'compatibility.json'
out_registries = root / 'catalog' / 'registries.json'

entries = []
compat_agents = {}
stage_counts = {'incubating': 0, 'active': 0, 'archived': 0}
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
        reviews_path = skill_dir / 'reviews.json'
        if reviews_path.exists():
            reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
            latest = {}
            for entry in (reviews.get('entries') or []):
                reviewer = entry.get('reviewer')
                if reviewer:
                    latest[reviewer] = entry
            approval_count = len([entry for entry in latest.values() if entry.get('decision') == 'approved'])
            rejection_count = len([entry for entry in latest.values() if entry.get('decision') == 'rejected'])
        else:
            approval_count = 0
            rejection_count = 0
        agent_compatible = meta.get('agent_compatible', [])
        item = {
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
            'snapshot_of': meta.get('snapshot_of'),
            'depends_on': meta.get('depends_on', []),
            'conflicts_with': meta.get('conflicts_with', []),
            'agent_compatible': agent_compatible,
            'installable': bool(meta.get('distribution', {}).get('installable', True)),
            'approval_count': approval_count,
            'rejection_count': rejection_count,
            'path': str(skill_dir.relative_to(root)),
            'source_registry': catalog_source_identity.get('registry_name'),
            'source_registry_url': catalog_source_identity.get('registry_url'),
            'source_registry_ref': catalog_source_identity.get('registry_ref'),
            'source_registry_commit': catalog_source_identity.get('registry_commit'),
            'source_registry_tag': catalog_source_identity.get('registry_tag'),
            'source_registry_trust': catalog_source_identity.get('registry_trust'),
            'source_update_mode': catalog_source_identity.get('registry_update_mode'),
            'source_pin_mode': catalog_source_identity.get('registry_pin_mode'),
            'source_pin_value': catalog_source_identity.get('registry_pin_value'),
            'expected_tag': expected_skill_tag(meta.get('name'), meta.get('version')),
        }
        entries.append(item)
        stage_counts[item['status']] = stage_counts.get(item['status'], 0) + 1
        for agent in agent_compatible:
            compat_agents.setdefault(agent, []).append({
                'name': item['name'],
                'version': item['version'],
                'status': item['status'],
                'path': item['path'],
            })

catalog = {
    'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
    'count': len(entries),
    'skills': entries,
}
active = {
    'generated_at': catalog['generated_at'],
    'count': sum(1 for entry in entries if entry['status'] == 'active' and entry['installable']),
    'skills': [entry for entry in entries if entry['status'] == 'active' and entry['installable']],
}
compatibility = {
    'generated_at': catalog['generated_at'],
    'stage_counts': stage_counts,
    'agents': {k: sorted(v, key=lambda x: (x['name'], x['version'] or '')) for k, v in sorted(compat_agents.items())},
}
registries_export = []
for reg in cfg.get('registries', []):
    item = dict(reg)
    lp = item.get('local_path')
    if lp:
        item['resolved_root'] = str((root / lp).resolve()) if not Path(lp).is_absolute() else str(Path(lp).resolve())
    elif item.get('kind') == 'git':
        item['resolved_root'] = str((root / '.cache' / 'registries' / item.get('name')).resolve())
    else:
        item['resolved_root'] = None
    identity = registry_identity(root, reg)
    item['resolved_ref'] = identity.get('registry_ref')
    item['resolved_commit'] = identity.get('registry_commit')
    item['resolved_tag'] = identity.get('registry_tag')
    item['resolved_origin_url'] = identity.get('registry_origin_url')
    registries_export.append(item)
registries_view = {
    'generated_at': catalog['generated_at'],
    'default_registry': cfg.get('default_registry'),
    'registries': registries_export,
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
write_if_changed(out_compat, compatibility)
write_if_changed(out_registries, registries_view)
PY
