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
    content = read(path)
    if needle not in content:
        fail(f'expected {path} to mention {needle!r}')


def main():
    guide = ROOT / 'docs' / 'ai' / 'usage-guide.md'

    assert_contains(guide, 'scripts/search-skills.sh')
    assert_contains(guide, 'scripts/recommend-skill.sh')
    assert_contains(guide, 'scripts/inspect-skill.sh')
    assert_contains(guide, 'scripts/publish-skill.sh')
    assert_contains(guide, 'scripts/pull-skill.sh')
    assert_contains(guide, 'scripts/check-skill.sh')
    assert_contains(guide, 'scripts/check-all.sh')
    assert_contains(guide, '--mode confirm')
    assert_contains(guide, 'workflow-drills.md')
    assert_contains(guide, 'agent-operations.md')
    assert_contains(guide, 'when to use')
    assert_contains(guide, 'verify')

    print('OK: usage guide docs checks passed')


if __name__ == '__main__':
    main()
