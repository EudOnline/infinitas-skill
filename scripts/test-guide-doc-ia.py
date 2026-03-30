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
    private_first_cutover = ROOT / 'docs' / 'guide' / 'private-first-cutover.md'
    trust_model = ROOT / 'docs' / 'guide' / 'trust-model.md'
    conventions = ROOT / 'docs' / 'guide' / 'conventions.md'
    old_private_first_cutover = ROOT / 'docs' / 'private-first-cutover.md'
    old_trust_model = ROOT / 'docs' / 'trust-model.md'
    old_conventions = ROOT / 'docs' / 'conventions.md'
    guide_index = ROOT / 'docs' / 'guide' / 'README.md'
    root_readme = ROOT / 'README.md'

    assert_exists(private_first_cutover)
    assert_exists(trust_model)
    assert_exists(conventions)
    assert_missing(old_private_first_cutover)
    assert_missing(old_trust_model)
    assert_missing(old_conventions)
    assert_contains(guide_index, '(private-first-cutover.md)')
    assert_contains(guide_index, '(trust-model.md)')
    assert_contains(guide_index, '(conventions.md)')
    assert_contains(root_readme, '(docs/guide/private-first-cutover.md)')
    assert_contains(private_first_cutover, 'source_of_truth:')
    assert_contains(trust_model, 'source_of_truth:')
    assert_contains(conventions, 'source_of_truth:')
    assert_contains(conventions, '../reference/metadata-schema.md')

    print('OK: guide document IA keeps maintained guide docs under docs/guide')


if __name__ == '__main__':
    main()
