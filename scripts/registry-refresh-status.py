#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from registry_refresh_state_lib import evaluate_refresh_status
from registry_source_lib import find_registry, load_registry_config, validate_registry_config

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('registry')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    cfg = load_registry_config(ROOT)
    errors = validate_registry_config(ROOT, cfg)
    if errors:
        fail('invalid registry-sources.json:\n- ' + '\n- '.join(errors))

    reg = find_registry(cfg, args.registry)
    if reg is None:
        fail(f'unknown registry: {args.registry}')

    status = evaluate_refresh_status(ROOT, reg)

    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return

    print(f"registry: {status.get('registry')}")
    print(f"kind: {status.get('kind')}")
    print(f"freshness_state: {status.get('freshness_state')}")
    print(f"has_state: {str(bool(status.get('has_state'))).lower()}")
    if status.get('refreshed_at'):
        print(f"refreshed_at: {status.get('refreshed_at')}")
    if status.get('age_hours') is not None:
        print(f"age_hours: {status.get('age_hours')}")
    if status.get('source_ref'):
        print(f"source_ref: {status.get('source_ref')}")
    if status.get('source_tag'):
        print(f"source_tag: {status.get('source_tag')}")
    if status.get('source_commit'):
        print(f"source_commit: {status.get('source_commit')}")


if __name__ == '__main__':
    main()
