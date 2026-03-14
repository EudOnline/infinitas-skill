#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / '.github' / 'workflows' / 'release-attestation.yml'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def main():
    if not WORKFLOW.exists():
        fail(f'missing workflow file: {WORKFLOW}')

    workflow = WORKFLOW.read_text(encoding='utf-8')
    required = [
        'workflow_dispatch',
        'workflow_call',
        'actions/checkout@v4',
        'actions/setup-python@v5',
        "python-version: '3.11'",
        'scripts/generate-provenance.py',
        'catalog/provenance',
        'GITHUB_SHA',
        'GITHUB_REF',
        'GITHUB_RUN_ID',
        'GITHUB_WORKFLOW',
        'actions/upload-artifact',
    ]
    for needle in required:
        if needle not in workflow:
            fail(f'missing workflow behavior: {needle}')

    print('OK: CI attestation workflow contract looks valid')


if __name__ == '__main__':
    main()
