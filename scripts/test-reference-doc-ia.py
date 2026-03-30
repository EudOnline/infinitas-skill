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
    old_registry_refresh_policy = ROOT / 'docs' / 'registry-refresh-policy.md'
    old_metadata_schema = ROOT / 'docs' / 'metadata-schema.md'
    reference_index = ROOT / 'docs' / 'reference' / 'README.md'
    ops_index = ROOT / 'docs' / 'ops' / 'README.md'
    conventions_doc = ROOT / 'docs' / 'conventions.md'

    assert_exists(registry_refresh_policy)
    assert_exists(metadata_schema)
    assert_missing(old_registry_refresh_policy)
    assert_missing(old_metadata_schema)
    assert_contains(reference_index, '(registry-refresh-policy.md)')
    assert_contains(reference_index, '(metadata-schema.md)')
    assert_contains(ops_index, '(../reference/registry-refresh-policy.md)')
    assert_contains(conventions_doc, 'docs/reference/metadata-schema.md')
    assert_contains(registry_refresh_policy, 'source_of_truth:')
    assert_contains(metadata_schema, 'source_of_truth:')

    print('OK: reference document IA keeps maintained reference docs under docs/reference')


if __name__ == '__main__':
    main()
