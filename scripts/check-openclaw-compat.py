#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from openclaw_bridge_lib import validate_exported_openclaw_dir  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill-dir', required=True)
    parser.add_argument('--public-ready', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    result = validate_exported_openclaw_dir(Path(args.skill_dir), public_ready=args.public_ready)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        if result['errors']:
            print('\n'.join(result['errors']), file=sys.stderr)
        else:
            print(f"OK: {args.skill_dir}")
    raise SystemExit(1 if result['errors'] else 0)


if __name__ == '__main__':
    main()
