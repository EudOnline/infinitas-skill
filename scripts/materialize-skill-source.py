#!/usr/bin/env python3
import argparse
import json
import sys

from distribution_lib import DistributionError, materialize_distribution_source


def parse_args():
    parser = argparse.ArgumentParser(description='Materialize a resolved skill source into a local directory')
    parser.add_argument('--source-json', required=True, help='Resolver JSON payload')
    return parser.parse_args()


def main():
    args = parse_args()
    source_info = json.loads(args.source_json)
    try:
        result = materialize_distribution_source(source_info)
    except DistributionError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
