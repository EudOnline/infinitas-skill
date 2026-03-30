#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAD_LINK_PATTERN = re.compile(r'/Users/.+?/\.worktrees/')


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def maintained_docs():
    candidates = [ROOT / 'README.md']
    for path in (ROOT / 'docs').rglob('*.md'):
        if 'plans' in path.parts or 'archive' in path.parts:
            continue
        candidates.append(path)
    return sorted(candidates)


def main():
    offenders = []
    for path in maintained_docs():
        text = path.read_text(encoding='utf-8')
        if BAD_LINK_PATTERN.search(text):
            offenders.append(path)

    if offenders:
        formatted = ', '.join(str(path) for path in offenders)
        fail(f'maintained docs must not contain absolute worktree links: {formatted}')

    print('OK: maintained docs avoid absolute worktree links')


if __name__ == '__main__':
    main()
