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
    readme = ROOT / 'README.md'
    docs_readme = ROOT / 'docs' / 'README.md'
    consume_skill = ROOT / 'skills' / 'active' / 'consume-infinitas-skill' / 'SKILL.md'
    consume_smoke = ROOT / 'skills' / 'active' / 'consume-infinitas-skill' / 'tests' / 'smoke.md'
    cli_reference = ROOT / 'docs' / 'reference' / 'cli-reference.md'

    assert_contains(readme, 'docs/reference/cli-reference.md')
    assert_contains(readme, 'uv run infinitas discovery')
    assert_contains(docs_readme, 'platform-contracts/README.md')
    assert_contains(consume_skill, 'uv run infinitas discovery recommend')
    assert_contains(consume_skill, 'uv run infinitas discovery inspect')
    assert_contains(consume_smoke, 'uv run infinitas discovery recommend')
    assert_contains(consume_smoke, '--mode confirm')
    assert_contains(cli_reference, 'infinitas discovery recommend')
    assert_contains(cli_reference, 'infinitas discovery inspect')

    print('OK: recommend docs checks passed')


if __name__ == '__main__':
    main()
