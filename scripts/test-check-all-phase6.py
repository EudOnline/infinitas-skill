#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def main():
    content = (ROOT / 'scripts' / 'check-all.sh').read_text(encoding='utf-8')
    for needle in [
        'python3 scripts/test-recommend-skill.py',
        'python3 scripts/test-recommend-docs.py',
    ]:
        if needle not in content:
            fail(f'expected check-all.sh to include {needle!r}')
    print('OK: check-all phase 6 coverage checks passed')


if __name__ == '__main__':
    main()
