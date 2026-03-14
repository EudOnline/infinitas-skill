#!/usr/bin/env python3
import argparse
import json
import sys

from attestation_lib import AttestationError, verify_ci_attestation


def parse_args():
    parser = argparse.ArgumentParser(description='Verify a CI-native release attestation against repo-managed policy')
    parser.add_argument('provenance', help='Path to the CI attestation JSON file')
    parser.add_argument('--json', action='store_true', help='Print machine-readable verification details')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = verify_ci_attestation(args.provenance)
    except AttestationError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"OK: verified {args.provenance} provider={result['provider']} "
            f"workflow={result['workflow']} run_id={result['run_id']}"
        )


if __name__ == '__main__':
    main()
