#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def read(path: Path) -> str:
    if not path.exists():
        fail(f'missing documentation file: {path}')
    return path.read_text(encoding='utf-8')


def assert_contains(path: Path, needle: str):
    if needle not in read(path):
        fail(f'expected {path} to mention {needle!r}')


def main():
    readme = ROOT / 'README.md'
    policy_packs = ROOT / 'docs' / 'reference' / 'policy-packs.md'

    assert_contains(readme, 'policy_trace')
    assert_contains(readme, 'validation_errors')
    assert_contains(readme, 'policy/team-policy.json')
    assert_contains(readme, 'uv run infinitas policy check-promotion <skill> --json')
    assert_contains(readme, 'uv run infinitas release check-state operate-infinitas-skill --json')
    assert_contains(readme, 'scripts/validate-registry.py --json')
    assert_contains(policy_packs, '--debug-policy')
    assert_contains(policy_packs, 'policy_trace')
    assert_contains(policy_packs, 'validation_errors')
    assert_contains(policy_packs, 'team_policy')
    assert_contains(policy_packs, 'owner_teams')
    assert_contains(policy_packs, 'policy/team-policy.json')
    assert_contains(policy_packs, 'effective_sources')
    assert_contains(policy_packs, 'blocking_rules')

    print('OK: policy trace docs checks passed')


if __name__ == '__main__':
    main()
