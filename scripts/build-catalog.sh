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

root = Path(os.environ['ROOT']).resolve()
sys.path.insert(0, str(root / 'scripts'))

from registry_source_lib import load_registry_config, registry_identity, registry_is_resolution_candidate, resolve_registry_root  # noqa: E402
from registry_snapshot_lib import snapshot_catalog_summary  # noqa: E402
from review_lib import ReviewPolicyError, evaluate_review_state, load_reviews  # noqa: E402
from skill_identity_lib import display_name, normalize_skill_identity  # noqa: E402
from distribution_lib import DistributionError, manifest_index_entry  # noqa: E402
from ai_index_lib import build_ai_index  # noqa: E402
from discovery_index_lib import build_discovery_index  # noqa: E402
from compatibility_evidence_lib import load_compatibility_evidence, merge_declared_and_verified_support  # noqa: E402


def expected_skill_tag(name, version):
    if not name or not version:
        return None
    return f'skill/{name}/v{version}'


def review_audit_entries(skill_dir):
    reviews = load_reviews(skill_dir)
    entries = []
    for item in reviews.get('entries', []):
        reviewer = item.get('reviewer')
        decision = item.get('decision')
        if not reviewer or not decision:
            continue
        entries.append({
            'reviewer': reviewer,
            'decision': decision,
            'at': item.get('at'),
            'note': item.get('note'),
        })
    return entries


cfg = load_registry_config(root)


def stable_catalog_identity(reg, identity):
    if not reg:
        return identity
    reg_root = resolve_registry_root(root, reg)
    if reg_root == root and identity.get('registry_update_mode') == 'local-only':
        # A committed catalog cannot stably point at the live HEAD of the same
        # repository that stores the catalog files, otherwise every commit would
        # invalidate catalog/registries.json (and per-skill source identity) on
        # the next check/build pass.
        clone = dict(identity)
        clone['registry_commit'] = None
        clone['registry_tag'] = None
        clone['registry_branch'] = None
        return clone
    return identity


catalog_source_registry = None
for reg in cfg.get('registries', []):
    if resolve_registry_root(root, reg) == root:
        catalog_source_registry = reg
        break
if catalog_source_registry is None:
    catalog_source_registry = next((reg for reg in cfg.get('registries', []) if reg.get('name') == cfg.get('default_registry')), None)
catalog_source_identity = stable_catalog_identity(
    catalog_source_registry,
    registry_identity(root, catalog_source_registry) if catalog_source_registry else {},
)

skills_root = root / 'skills'
out_catalog = root / 'catalog' / 'catalog.json'
out_active = root / 'catalog' / 'active.json'
out_compat = root / 'catalog' / 'compatibility.json'
out_registries = root / 'catalog' / 'registries.json'
out_distributions = root / 'catalog' / 'distributions.json'
out_ai_index = root / 'catalog' / 'ai-index.json'
out_discovery_index = root / 'catalog' / 'discovery-index.json'
out_inventory_export = root / 'catalog' / 'inventory-export.json'
out_audit_export = root / 'catalog' / 'audit-export.json'


def dist_identity_key(entry):
    return (entry.get('qualified_name') or entry.get('name'), entry.get('version'))


def load_json_if_exists(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


distribution_entries = []
distribution_lookup = {}
distribution_root = root / 'catalog' / 'distributions'
if distribution_root.exists():
    for manifest_path in sorted(distribution_root.rglob('manifest.json')):
        try:
            entry = manifest_index_entry(manifest_path, root)
        except DistributionError as exc:
            print(f'FAIL: {exc}', file=sys.stderr)
            raise SystemExit(1)
        distribution_entries.append(entry)
        distribution_lookup[dist_identity_key(entry)] = entry

try:
    compatibility_evidence = load_compatibility_evidence(root)
except ValueError as exc:
    print(f'FAIL: {exc}', file=sys.stderr)
    raise SystemExit(1)

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
        try:
            review_status = evaluate_review_state(skill_dir, root=root)
        except ReviewPolicyError as exc:
            for error in exc.errors:
                print(f'FAIL: {error}', file=sys.stderr)
            raise SystemExit(1)
        agent_compatible = meta.get('agent_compatible', [])
        identity = normalize_skill_identity(meta)
        review_audit = review_audit_entries(skill_dir)
        item = {
            'name': meta.get('name', skill_dir.name),
            'publisher': identity.get('publisher'),
            'qualified_name': identity.get('qualified_name'),
            'identity_mode': identity.get('identity_mode'),
            'version': meta.get('version'),
            'status': meta.get('status', stage),
            'summary': meta.get('summary', ''),
            'author': identity.get('author'),
            'owner': meta.get('owner'),
            'owners': identity.get('owners', []),
            'maintainers': meta.get('maintainers', []),
            'tags': meta.get('tags', []),
            'review_state': review_status.get('effective_review_state'),
            'declared_review_state': review_status.get('declared_review_state'),
            'risk_level': meta.get('risk_level'),
            'derived_from': meta.get('derived_from'),
            'snapshot_of': meta.get('snapshot_of'),
            'depends_on': meta.get('depends_on', []),
            'conflicts_with': meta.get('conflicts_with', []),
            'agent_compatible': agent_compatible,
            'installable': bool(meta.get('distribution', {}).get('installable', True)),
            'approval_count': review_status.get('approval_count'),
            'rejection_count': review_status.get('rejection_count'),
            'blocking_rejection_count': review_status.get('blocking_rejection_count'),
            'required_approvals': review_status.get('required_approvals'),
            'quorum_met': review_status.get('quorum_met'),
            'review_gate_pass': review_status.get('review_gate_pass'),
            'required_reviewer_groups': review_status.get('required_groups'),
            'covered_reviewer_groups': review_status.get('covered_groups'),
            'missing_reviewer_groups': review_status.get('missing_groups'),
            'reviewers': review_audit,
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
        dist = distribution_lookup.get(dist_identity_key(item))
        if dist:
            item['verified_distribution'] = {
                'manifest_path': dist.get('manifest_path'),
                'bundle_path': dist.get('bundle_path'),
                'bundle_sha256': dist.get('bundle_sha256'),
                'attestation_path': dist.get('attestation_path'),
                'attestation_signature_path': dist.get('attestation_signature_path'),
                'source_snapshot_tag': dist.get('source_snapshot_tag'),
                'source_snapshot_commit': dist.get('source_snapshot_commit'),
                'generated_at': dist.get('generated_at'),
            }
        item = merge_declared_and_verified_support(item, compatibility_evidence)
        entries.append(item)
        stage_counts[item['status']] = stage_counts.get(item['status'], 0) + 1
        for agent in agent_compatible:
            compat_agents.setdefault(agent, []).append({
                'name': item['name'],
                'publisher': item['publisher'],
                'qualified_name': item['qualified_name'],
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
    'skills': [
        {
            'name': entry.get('name'),
            'publisher': entry.get('publisher'),
            'qualified_name': entry.get('qualified_name'),
            'version': entry.get('version'),
            'status': entry.get('status'),
            'path': entry.get('path'),
            'declared_support': entry.get('declared_support') or [],
            'verified_support': entry.get('verified_support') or {},
        }
        for entry in sorted(entries, key=lambda x: (x.get('name') or '', x.get('version') or ''))
    ],
}
registries_export = []
for reg in cfg.get('registries', []):
    item = dict(reg)
    reg_root = resolve_registry_root(root, reg)
    if reg_root == root and (reg.get('update_policy') or {}).get('mode') == 'local-only':
        item['resolved_root'] = '.'
    else:
        lp = item.get('local_path')
        if lp:
            item['resolved_root'] = str((root / lp).resolve()) if not Path(lp).is_absolute() else str(Path(lp).resolve())
        elif item.get('kind') == 'git':
            item['resolved_root'] = str((root / '.cache' / 'registries' / item.get('name')).resolve())
        else:
            item['resolved_root'] = None
    identity = stable_catalog_identity(reg, registry_identity(root, reg))
    item['resolved_ref'] = identity.get('registry_ref')
    item['resolved_commit'] = identity.get('registry_commit')
    item['resolved_tag'] = identity.get('registry_tag')
    item['resolved_origin_url'] = identity.get('registry_origin_url')
    item['resolved_federation_mode'] = identity.get('registry_federation_mode')
    item['resolved_allowed_publishers'] = identity.get('registry_allowed_publishers')
    item['resolved_publisher_map'] = identity.get('registry_publisher_map')
    item['resolved_require_immutable_artifacts'] = identity.get('registry_require_immutable_artifacts')
    item['resolver_candidate'] = registry_is_resolution_candidate(reg)
    item.update(snapshot_catalog_summary(root, reg.get('name')))
    registries_export.append(item)
registries_view = {
    'generated_at': catalog['generated_at'],
    'default_registry': cfg.get('default_registry'),
    'registries': registries_export,
}
distributions_view = {
    'generated_at': catalog['generated_at'],
    'count': len(distribution_entries),
    'skills': distribution_entries,
}
ai_index = build_ai_index(root=root, catalog_entries=entries, distribution_entries=distribution_entries)
ai_index['generated_at'] = catalog['generated_at']
discovery_index = build_discovery_index(root=root, local_ai_index=ai_index, registry_config=cfg)
discovery_index['generated_at'] = catalog['generated_at']

registry_by_name = {item.get('name'): item for item in registries_export if isinstance(item, dict) and item.get('name')}

inventory_skills = []
for entry in entries:
    source_registry = registry_by_name.get(entry.get('source_registry'))
    verified_distribution = entry.get('verified_distribution') or {}
    inventory_skills.append(
        {
            'name': entry.get('name'),
            'publisher': entry.get('publisher'),
            'qualified_name': entry.get('qualified_name'),
            'identity_mode': entry.get('identity_mode'),
            'version': entry.get('version'),
            'status': entry.get('status'),
            'summary': entry.get('summary'),
            'path': entry.get('path'),
            'installable': bool(entry.get('installable', False)),
            'released': bool(verified_distribution.get('attestation_path')),
            'source_registry': entry.get('source_registry'),
            'source_registry_url': entry.get('source_registry_url'),
            'source_registry_trust': entry.get('source_registry_trust'),
            'source_registry_ref': entry.get('source_registry_ref'),
            'source_registry_commit': entry.get('source_registry_commit'),
            'source_registry_tag': entry.get('source_registry_tag'),
            'source_update_mode': entry.get('source_update_mode'),
            'source_pin_mode': entry.get('source_pin_mode'),
            'source_pin_value': entry.get('source_pin_value'),
            'source_federation_mode': source_registry.get('resolved_federation_mode') if source_registry else None,
            'resolver_candidate': source_registry.get('resolver_candidate') if source_registry else None,
            'distribution_manifest_path': verified_distribution.get('manifest_path'),
            'distribution_bundle_path': verified_distribution.get('bundle_path'),
            'release_attestation_path': verified_distribution.get('attestation_path'),
            'release_attestation_signature_path': verified_distribution.get('attestation_signature_path'),
            'release_source_snapshot_tag': verified_distribution.get('source_snapshot_tag'),
            'release_source_snapshot_commit': verified_distribution.get('source_snapshot_commit'),
        }
    )

inventory_export = {
    '$schema': '../schemas/inventory-export.schema.json',
    'schema_version': 1,
    'generated_at': catalog['generated_at'],
    'default_registry': cfg.get('default_registry'),
    'counts': {
        'registries': len(registries_export),
        'skills': len(inventory_skills),
        'installable_skills': sum(1 for item in inventory_skills if item.get('installable')),
        'released_skills': sum(1 for item in inventory_skills if item.get('released')),
    },
    'registries': [
        {
            'name': item.get('name'),
            'kind': item.get('kind'),
            'priority': item.get('priority'),
            'enabled': item.get('enabled'),
            'trust': item.get('trust'),
            'resolver_candidate': item.get('resolver_candidate'),
            'federation_mode': item.get('resolved_federation_mode'),
            'allowed_publishers': item.get('resolved_allowed_publishers'),
            'publisher_map': item.get('resolved_publisher_map'),
            'require_immutable_artifacts': item.get('resolved_require_immutable_artifacts'),
            'resolved_root': item.get('resolved_root'),
            'resolved_ref': item.get('resolved_ref'),
            'resolved_commit': item.get('resolved_commit'),
            'resolved_tag': item.get('resolved_tag'),
            'resolved_origin_url': item.get('resolved_origin_url'),
        }
        for item in registries_export
    ],
    'skills': sorted(inventory_skills, key=lambda item: (item.get('qualified_name') or '', item.get('version') or '')),
}

audit_releases = []
for entry in sorted(distribution_entries, key=lambda item: (item.get('qualified_name') or item.get('name') or '', item.get('version') or '')):
    provenance_ref = entry.get('attestation_path')
    if not provenance_ref:
        continue
    provenance_payload = load_json_if_exists(root / provenance_ref)
    if not isinstance(provenance_payload, dict):
        continue
    audit_releases.append(
        {
            'name': entry.get('name'),
            'publisher': entry.get('publisher'),
            'qualified_name': entry.get('qualified_name'),
            'identity_mode': entry.get('identity_mode'),
            'version': entry.get('version'),
            'status': entry.get('status'),
            'provenance_path': provenance_ref,
            'signature_path': entry.get('attestation_signature_path'),
            'manifest_path': entry.get('manifest_path'),
            'bundle_path': entry.get('bundle_path'),
            'bundle_sha256': entry.get('bundle_sha256'),
            'bundle_size': entry.get('bundle_size'),
            'source_snapshot': provenance_payload.get('source_snapshot') or {},
            'review': provenance_payload.get('review') or {},
            'release': provenance_payload.get('release') or {},
            'registry': provenance_payload.get('registry') or {},
            'dependencies': provenance_payload.get('dependencies') or {},
        }
    )

audit_export = {
    '$schema': '../schemas/audit-export.schema.json',
    'schema_version': 1,
    'generated_at': catalog['generated_at'],
    'counts': {
        'releases': len(audit_releases),
    },
    'releases': audit_releases,
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
write_if_changed(out_distributions, distributions_view)
write_if_changed(out_ai_index, ai_index)
write_if_changed(out_discovery_index, discovery_index)
write_if_changed(out_inventory_export, inventory_export)
write_if_changed(out_audit_export, audit_export)
PY
