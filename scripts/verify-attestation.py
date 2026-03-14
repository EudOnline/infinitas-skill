#!/usr/bin/env python3
import argparse
import json
import sys

from attestation_lib import AttestationError, verify_attestation


def parse_args():
    parser = argparse.ArgumentParser(description='Verify a release attestation against repo-managed SSH and CI policy')
    parser.add_argument('provenance', help='Path to the attestation JSON file')
    parser.add_argument('--identity', help='Override signer identity (defaults to attestation.signer_identity)')
    parser.add_argument('--allowed-signers', help='Override allowed signers file path')
    parser.add_argument('--namespace', help='Override SSH signature namespace')
    parser.add_argument('--json', action='store_true', help='Print machine-readable verification details')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        result = verify_attestation(
            args.provenance,
            identity=args.identity,
            allowed_signers=args.allowed_signers,
            namespace=args.namespace,
        )
    except AttestationError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"OK: verified {args.provenance} with signer={result['identity']} namespace={result['namespace']}")


if __name__ == '__main__':
    main()
