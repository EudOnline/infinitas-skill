#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FIELDS = ['audience', 'owner', 'source_of_truth', 'last_reviewed', 'status']
TARGETS = [
    ROOT / 'docs' / 'ops' / 'README.md',
    ROOT / 'docs' / 'ops' / 'server-deployment.md',
    ROOT / 'docs' / 'ops' / 'server-backup-and-restore.md',
]


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def parse_front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != '---':
        fail(f'missing front matter start marker in {path}')

    metadata = {}
    for line in lines[1:]:
        stripped = line.strip()
        if stripped == '---':
            return metadata
        if ':' not in stripped:
            fail(f'invalid front matter line in {path}: {line!r}')
        key, value = stripped.split(':', 1)
        metadata[key.strip()] = value.strip()

    fail(f'missing front matter end marker in {path}')


def main():
    for path in TARGETS:
        if not path.exists():
            fail(f'missing expected maintained doc: {path}')
        metadata = parse_front_matter(path)
        for field in REQUIRED_FIELDS:
            if not metadata.get(field):
                fail(f'missing required metadata field {field!r} in {path}')

    print('OK: maintained ops docs include required metadata front matter')


if __name__ == '__main__':
    main()
