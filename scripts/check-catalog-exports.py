#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        fail(f'could not parse JSON from {path}: {exc}')


def main():
    inventory_path = ROOT / 'catalog' / 'inventory-export.json'
    audit_path = ROOT / 'catalog' / 'audit-export.json'
    catalog_path = ROOT / 'catalog' / 'catalog.json'
    registries_path = ROOT / 'catalog' / 'registries.json'
    distributions_path = ROOT / 'catalog' / 'distributions.json'

    for path in [inventory_path, audit_path, catalog_path, registries_path, distributions_path]:
        if not path.exists():
            fail(f'missing expected catalog artifact: {path}')

    inventory = load_json(inventory_path)
    audit = load_json(audit_path)
    catalog = load_json(catalog_path)
    registries = load_json(registries_path)
    distributions = load_json(distributions_path)

    if inventory.get('schema_version') != 1:
        fail(f"inventory export schema_version must be 1, got {inventory.get('schema_version')!r}")
    if audit.get('schema_version') != 1:
        fail(f"audit export schema_version must be 1, got {audit.get('schema_version')!r}")

    inventory_registries = inventory.get('registries')
    if not isinstance(inventory_registries, list):
        fail('inventory export registries must be an array')
    registry_names = {item.get('name') for item in registries.get('registries') or [] if isinstance(item, dict) and item.get('name')}
    inventory_registry_names = {item.get('name') for item in inventory_registries if isinstance(item, dict) and item.get('name')}
    if inventory_registry_names != registry_names:
        fail(f'inventory export registry names mismatch: {sorted(inventory_registry_names)!r} != {sorted(registry_names)!r}')

    catalog_skills = {
        ((item.get('qualified_name') or item.get('name')), item.get('version')): item
        for item in catalog.get('skills') or []
        if isinstance(item, dict)
    }
    inventory_skills = inventory.get('skills')
    if not isinstance(inventory_skills, list):
        fail('inventory export skills must be an array')
    inventory_skill_keys = {
        ((item.get('qualified_name') or item.get('name')), item.get('version'))
        for item in inventory_skills
        if isinstance(item, dict)
    }
    if inventory_skill_keys != set(catalog_skills):
        fail('inventory export skill identities must match catalog skill identities')

    released_skill_count = 0
    for key, item in catalog_skills.items():
        exported = next(
            (
                candidate for candidate in inventory_skills
                if isinstance(candidate, dict)
                and (candidate.get('qualified_name') or candidate.get('name'), candidate.get('version')) == key
            ),
            None,
        )
        if exported is None:
            fail(f'missing inventory export for skill {key!r}')
        if exported.get('source_registry') != item.get('source_registry'):
            fail(f'inventory export source_registry mismatch for {key!r}')
        if exported.get('source_registry_trust') != item.get('source_registry_trust'):
            fail(f'inventory export source_registry_trust mismatch for {key!r}')
        expected_release = bool((item.get('verified_distribution') or {}).get('attestation_path'))
        if bool(exported.get('released')) != expected_release:
            fail(f'inventory export released flag mismatch for {key!r}')
        if expected_release:
            released_skill_count += 1

    counts = inventory.get('counts') or {}
    if counts.get('skills') != len(catalog_skills):
        fail(f"inventory export counts.skills mismatch: {counts.get('skills')!r}")
    if counts.get('released_skills') != released_skill_count:
        fail(f"inventory export counts.released_skills mismatch: {counts.get('released_skills')!r}")

    distribution_entries = {
        ((item.get('qualified_name') or item.get('name')), item.get('version')): item
        for item in distributions.get('skills') or []
        if isinstance(item, dict)
    }
    releases = audit.get('releases')
    if not isinstance(releases, list):
        fail('audit export releases must be an array')
    if (audit.get('counts') or {}).get('releases') != len(releases):
        fail('audit export counts.releases must match release entry count')

    for item in releases:
        if not isinstance(item, dict):
            fail(f'audit export release entries must be objects, got {item!r}')
        key = ((item.get('qualified_name') or item.get('name')), item.get('version'))
        dist = distribution_entries.get(key)
        if dist is None:
            fail(f'audit export release has no matching distribution entry: {key!r}')
        if item.get('provenance_path') != dist.get('attestation_path'):
            fail(f'audit export provenance_path mismatch for {key!r}')
        if item.get('signature_path') != dist.get('attestation_signature_path'):
            fail(f'audit export signature_path mismatch for {key!r}')
        if not isinstance(item.get('source_snapshot') or {}, dict):
            fail(f'audit export source_snapshot must be an object for {key!r}')

    print(
        f"OK: catalog exports checked ({len(inventory_registries)} registries, "
        f"{len(inventory_skills)} skills, {len(releases)} release entries)"
    )


if __name__ == '__main__':
    main()
