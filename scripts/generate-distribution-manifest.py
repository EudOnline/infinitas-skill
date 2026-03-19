#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from distribution_lib import DistributionError, build_distribution_manifest_payload
from release_lib import ROOT


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a verified distribution manifest from a signed attestation payload')
    parser.add_argument('--provenance', required=True, help='Path to the attestation JSON file')
    parser.add_argument('--bundle', required=True, help='Path to the bundled skill artifact')
    parser.add_argument('--output', help='Write manifest JSON to this path instead of stdout')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        payload = build_distribution_manifest_payload(args.provenance, args.bundle, root=ROOT, attestation_root=ROOT)
    except DistributionError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1

    text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
