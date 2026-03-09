#!/usr/bin/env python3
import argparse
import json
import sys

from distribution_lib import DistributionError, verify_distribution_manifest


def parse_args():
    parser = argparse.ArgumentParser(description='Verify a stable distribution manifest against the signed attestation payload and bundle')
    parser.add_argument('manifest', help='Path to the distribution manifest JSON file')
    parser.add_argument('--json', action='store_true', help='Print machine-readable verification details')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = verify_distribution_manifest(args.manifest)
    except DistributionError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"OK: verified {args.manifest} for {result['skill']}@{result['version']} using {result['attestation']['identity']}"
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
