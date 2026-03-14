#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def assert_contains(path: Path, needles):
    text = path.read_text(encoding='utf-8')
    for needle in needles:
        if needle not in text:
            fail(f'missing {needle!r} in {path}')


def main():
    assert_contains(
        ROOT / 'docs' / 'ai' / 'ci-attestation.md',
        [
            'Offline verification',
            'Online verification',
            'scripts/verify-attestation.py',
            'scripts/verify-ci-attestation.py',
            'scripts/verify-distribution-manifest.py',
            '`ssh`',
            '`ci`',
            '`both`',
        ],
    )
    assert_contains(
        ROOT / 'docs' / 'ai' / 'publish.md',
        ['release_trust_mode', 'CI-native attestation', 'scripts/verify-ci-attestation.py'],
    )
    assert_contains(
        ROOT / 'docs' / 'ai' / 'pull.md',
        ['required_formats', 'scripts/verify-distribution-manifest.py', 'CI attestation'],
    )
    assert_contains(
        ROOT / 'docs' / 'release-checklist.md',
        ['CI attestation', '`release_trust_mode`', '`both`'],
    )
    assert_contains(
        ROOT / 'README.md',
        ['scripts/verify-ci-attestation.py', 'release-attestation.yml', 'CI-native attestation'],
    )
    print('OK: CI attestation docs checks passed')


if __name__ == '__main__':
    main()
