#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def assert_contains(path: Path, needle: str):
    text = path.read_text(encoding='utf-8')
    if needle not in text:
        fail(f'expected {path} to contain {needle!r}')


def main():
    assert_contains(ROOT / 'README.md', 'policy/policy-packs.json')
    assert_contains(ROOT / 'docs' / 'reference' / 'policy-packs.md', 'repository-local files win over packs')
    assert_contains(ROOT / 'docs' / 'reference' / 'policy-packs.md', 'policy/packs/')
    assert_contains(ROOT / 'docs' / 'reference' / 'promotion-policy.md', 'policy/policy-packs.json')
    assert_contains(ROOT / 'docs' / 'ops' / 'signing-bootstrap.md', 'policy/policy-packs.json')
    assert_contains(ROOT / 'docs' / 'reference' / 'multi-registry.md', 'policy/policy-packs.json')
    assert_contains(ROOT / 'scripts' / 'check-all.sh', 'python3 scripts/check-policy-packs.py')
    print('OK: policy-pack docs checks passed')


if __name__ == '__main__':
    main()
