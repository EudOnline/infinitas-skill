#!/usr/bin/env python3
import argparse
import json
import sys

from installed_integrity_lib import InstalledIntegrityError, verify_installed_skill


def parse_args():
    parser = argparse.ArgumentParser(description='Verify one installed skill directory against its recorded immutable distribution source')
    parser.add_argument('skill', help='Installed skill name or qualified name')
    parser.add_argument('target_dir', help='Installed skills target directory')
    parser.add_argument('--json', action='store_true', help='Print machine-readable verification details')
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        payload = verify_installed_skill(args.target_dir, args.skill)
    except InstalledIntegrityError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        'state': 'failed',
                        'skill': args.skill,
                        'target_dir': args.target_dir,
                        'error': str(exc),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f'FAIL: {exc}', file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif payload['state'] == 'verified':
        print(
            f"OK: verified {payload['qualified_name']}@{payload['installed_version']} "
            f"({payload['release_file_manifest_count']} files checked)"
        )
    else:
        print(
            f"FAIL: installed skill drifted for {payload['qualified_name']} "
            f"(modified={len(payload['modified_files'])}, missing={len(payload['missing_files'])}, "
            f"unexpected={len(payload['unexpected_files'])})",
            file=sys.stderr,
        )
    return 0 if payload['state'] == 'verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
