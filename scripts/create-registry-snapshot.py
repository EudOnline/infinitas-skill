#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from registry_snapshot_lib import create_snapshot
from registry_source_lib import find_registry, load_registry_config, validate_registry_config

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('registry')
    parser.add_argument('--snapshot-id')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    cfg = load_registry_config(ROOT)
    errors = validate_registry_config(ROOT, cfg)
    if errors:
        fail('invalid registry-sources.json:\n- ' + '\n- '.join(errors))

    reg = find_registry(cfg, args.registry)
    if reg is None:
        fail(f'unknown registry: {args.registry}')

    try:
        payload = create_snapshot(ROOT, reg, snapshot_id=args.snapshot_id)
    except ValueError as exc:
        fail(str(exc))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(payload.get('snapshot_root'))


if __name__ == '__main__':
    main()
