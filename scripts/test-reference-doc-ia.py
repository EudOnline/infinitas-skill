#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def assert_exists(path: Path):
    if not path.exists():
        fail(f'expected doc to exist: {path}')


def assert_missing(path: Path):
    if path.exists():
        fail(f'expected legacy root doc to be removed: {path}')


def assert_contains(path: Path, needle: str):
    text = path.read_text(encoding='utf-8')
    if needle not in text:
        fail(f'expected {path} to contain {needle!r}')


def main():
    registry_refresh_policy = ROOT / 'docs' / 'reference' / 'registry-refresh-policy.md'
    metadata_schema = ROOT / 'docs' / 'reference' / 'metadata-schema.md'
    distribution_manifests = ROOT / 'docs' / 'reference' / 'distribution-manifests.md'
    promotion_policy = ROOT / 'docs' / 'reference' / 'promotion-policy.md'
    policy_packs = ROOT / 'docs' / 'reference' / 'policy-packs.md'
    old_registry_refresh_policy = ROOT / 'docs' / 'registry-refresh-policy.md'
    old_metadata_schema = ROOT / 'docs' / 'metadata-schema.md'
    old_distribution_manifests = ROOT / 'docs' / 'distribution-manifests.md'
    old_promotion_policy = ROOT / 'docs' / 'promotion-policy.md'
    old_policy_packs = ROOT / 'docs' / 'policy-packs.md'
    reference_index = ROOT / 'docs' / 'reference' / 'README.md'
    ops_index = ROOT / 'docs' / 'ops' / 'README.md'
    conventions_doc = ROOT / 'docs' / 'conventions.md'

    assert_exists(registry_refresh_policy)
    assert_exists(metadata_schema)
    assert_exists(distribution_manifests)
    assert_exists(promotion_policy)
    assert_exists(policy_packs)
    assert_missing(old_registry_refresh_policy)
    assert_missing(old_metadata_schema)
    assert_missing(old_distribution_manifests)
    assert_missing(old_promotion_policy)
    assert_missing(old_policy_packs)
    assert_contains(reference_index, '(registry-refresh-policy.md)')
    assert_contains(reference_index, '(metadata-schema.md)')
    assert_contains(reference_index, '(distribution-manifests.md)')
    assert_contains(reference_index, '(promotion-policy.md)')
    assert_contains(reference_index, '(policy-packs.md)')
    assert_contains(ops_index, '(../reference/registry-refresh-policy.md)')
    assert_contains(conventions_doc, 'docs/reference/metadata-schema.md')
    assert_contains(registry_refresh_policy, 'source_of_truth:')
    assert_contains(metadata_schema, 'source_of_truth:')
    assert_contains(distribution_manifests, 'source_of_truth:')
    assert_contains(promotion_policy, 'source_of_truth:')
    assert_contains(policy_packs, 'source_of_truth:')

    print('OK: reference document IA keeps maintained reference docs under docs/reference')


if __name__ == '__main__':
    main()
