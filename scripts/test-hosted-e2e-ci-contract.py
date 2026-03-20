#!/usr/bin/env python3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / '.github' / 'workflows' / 'validate.yml'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def assert_contains(content: str, needle: str, *, label: str):
    if needle not in content:
        fail(f'expected {label} to include {needle!r}')


def main():
    if not WORKFLOW.exists():
        fail(f'missing workflow file: {WORKFLOW}')

    workflow = WORKFLOW.read_text(encoding='utf-8')
    for needle in [
        'actions/checkout@v4',
        'actions/setup-python@v5',
        "python-version: '3.11'",
        'python3 -m pip install --upgrade pip',
        'python3 -m pip install .',
        'scripts/check-all.sh',
        'INFINITAS_REQUIRE_HOSTED_E2E_TESTS: 1',
    ]:
        assert_contains(workflow, needle, label='validate workflow')

    check_all = (ROOT / 'scripts' / 'check-all.sh').read_text(encoding='utf-8')
    for needle in [
        'python3 scripts/test-hosted-registry-e2e.py',
        'import fastapi',
        'import httpx',
        'import jinja2',
        'import sqlalchemy',
        'import uvicorn',
        'INFINITAS_REQUIRE_HOSTED_E2E_TESTS',
    ]:
        assert_contains(check_all, needle, label='check-all.sh')

    print('OK: hosted e2e CI contract checks passed')


if __name__ == '__main__':
    main()
