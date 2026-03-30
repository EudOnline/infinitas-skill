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
    guide_doc = ROOT / 'docs' / 'guide' / 'private-first-cutover.md'
    old_doc = ROOT / 'docs' / 'private-first-cutover.md'
    guide_index = ROOT / 'docs' / 'guide' / 'README.md'
    root_readme = ROOT / 'README.md'

    assert_exists(guide_doc)
    assert_missing(old_doc)
    assert_contains(guide_index, '(private-first-cutover.md)')
    assert_contains(root_readme, '(docs/guide/private-first-cutover.md)')
    assert_contains(guide_doc, 'source_of_truth:')

    print('OK: guide document IA keeps private-first cutover under docs/guide')


if __name__ == '__main__':
    main()
