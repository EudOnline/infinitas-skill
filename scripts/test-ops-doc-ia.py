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
    signing_bootstrap = ROOT / 'docs' / 'ops' / 'signing-bootstrap.md'
    signing_operations = ROOT / 'docs' / 'ops' / 'signing-operations.md'
    release_checklist = ROOT / 'docs' / 'ops' / 'release-checklist.md'
    platform_drift_playbook = ROOT / 'docs' / 'ops' / 'platform-drift-playbook.md'
    federation_operations = ROOT / 'docs' / 'ops' / 'federation-operations.md'
    old_bootstrap = ROOT / 'docs' / 'signing-bootstrap.md'
    old_operations = ROOT / 'docs' / 'signing-operations.md'
    old_release_checklist = ROOT / 'docs' / 'release-checklist.md'
    old_platform_drift_playbook = ROOT / 'docs' / 'platform-drift-playbook.md'
    old_federation_operations = ROOT / 'docs' / 'federation-operations.md'
    ops_index = ROOT / 'docs' / 'ops' / 'README.md'

    assert_exists(signing_bootstrap)
    assert_exists(signing_operations)
    assert_exists(release_checklist)
    assert_exists(platform_drift_playbook)
    assert_exists(federation_operations)
    assert_missing(old_bootstrap)
    assert_missing(old_operations)
    assert_missing(old_release_checklist)
    assert_missing(old_platform_drift_playbook)
    assert_missing(old_federation_operations)
    assert_contains(ops_index, '(signing-bootstrap.md)')
    assert_contains(ops_index, '(signing-operations.md)')
    assert_contains(ops_index, '(release-checklist.md)')
    assert_contains(ops_index, '(platform-drift-playbook.md)')
    assert_contains(ops_index, '(federation-operations.md)')
    assert_contains(signing_bootstrap, 'source_of_truth:')
    assert_contains(signing_operations, 'source_of_truth:')
    assert_contains(release_checklist, 'source_of_truth:')
    assert_contains(platform_drift_playbook, 'source_of_truth:')
    assert_contains(federation_operations, 'source_of_truth:')

    print('OK: ops document IA keeps maintained runbooks under docs/ops')


if __name__ == '__main__':
    main()
