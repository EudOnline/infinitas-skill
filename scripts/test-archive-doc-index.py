#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

AUDIT_DOCS = [
    'dark-mode-audit.md',
    'layout-audit.md',
    'layout-conflicts-fixed.md',
    'override-fix-report.md',
]
DESIGN_DOCS = [
    'kawaii-color-research.md',
    'kawaii-enhancement-plan.md',
    'kawaii-theme-demo.md',
    'kawaii-theme-design.md',
    'theme-preview.md',
    'theme-migration-guide.md',
    'ui-ux-analysis-and-rebuild.md',
    'v2-migration-guide.md',
]


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def assert_exists(path: Path):
    if not path.exists():
        fail(f'expected archived doc to exist: {path}')


def assert_missing(path: Path):
    if path.exists():
        fail(f'expected root legacy doc to be removed: {path}')


def assert_contains(path: Path, needle: str):
    text = path.read_text(encoding='utf-8')
    if needle not in text:
        fail(f'expected {path} to contain {needle!r}')


def main():
    archive_index = ROOT / 'docs' / 'archive' / 'README.md'

    for name in AUDIT_DOCS:
        assert_missing(ROOT / 'docs' / name)
        assert_exists(ROOT / 'docs' / 'archive' / 'audits' / name)

    for name in DESIGN_DOCS:
        assert_missing(ROOT / 'docs' / name)
        assert_exists(ROOT / 'docs' / 'archive' / 'design' / name)

    assert_contains(archive_index, '(design/ui-ux-analysis-and-rebuild.md)')
    assert_contains(archive_index, '(design/theme-migration-guide.md)')
    assert_contains(archive_index, '(audits/dark-mode-audit.md)')

    print('OK: archive index tracks legacy design and audit docs')


if __name__ == '__main__':
    main()
