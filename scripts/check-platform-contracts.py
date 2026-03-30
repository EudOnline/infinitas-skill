#!/usr/bin/env python3
import argparse
import sys
from datetime import date
from pathlib import Path

from platform_contract_lib import load_platform_profile_contract, validate_platform_contract

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = {
    'claude': 'Claude Platform Contract',
    'codex': 'Codex Platform Contract',
    'openclaw': 'OpenClaw Platform Contract',
}


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)


def warn(message):
    print(f'WARN: {message}', file=sys.stderr)


def check_doc(path: Path, title: str, *, max_age_days: int | None, stale_policy: str) -> tuple[int, int]:
    errors = 0
    warnings = 0
    payload, validation_errors = validate_platform_contract(path, title)
    for message in validation_errors:
        fail(message)
    errors += len(validation_errors)

    profile_path = ROOT / 'profiles' / f'{path.stem}.json'
    profile_payload, profile_errors = load_platform_profile_contract(profile_path, path.stem)
    for message in profile_errors:
        fail(message)
    errors += len(profile_errors)

    doc_sources = payload.get('official_sources') or []
    profile_sources = profile_payload.get('sources') or []
    if doc_sources and profile_sources and profile_sources != doc_sources:
        fail(f'{profile_path}: contract.sources do not match {path}: {profile_sources!r} != {doc_sources!r}')
        errors += 1

    verified_date = payload.get('last_verified')
    profile_last_verified = profile_payload.get('last_verified')
    if isinstance(verified_date, date) and profile_last_verified and profile_last_verified != verified_date.isoformat():
        fail(
            f'{profile_path}: contract.last_verified {profile_last_verified!r} does not match '
            f'{path} {verified_date.isoformat()!r}'
        )
        errors += 1

    if isinstance(verified_date, date) and max_age_days is not None:
        age_days = (date.today() - verified_date).days
        if age_days > max_age_days:
            message = f'{path}: last verified {verified_date.isoformat()} is {age_days} days old (threshold {max_age_days})'
            if stale_policy == 'fail':
                fail(message)
                errors += 1
            else:
                warn(message)
                warnings += 1

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description='Check platform contract-watch documents.')
    parser.add_argument('--max-age-days', type=int, default=None, help='Warn when Last verified is older than this many days.')
    parser.add_argument(
        '--stale-policy',
        choices=['warn', 'fail'],
        default='warn',
        help='Whether over-age contract docs should warn or fail.',
    )
    args = parser.parse_args()

    errors = 0
    warnings = 0
    for slug, title in REQUIRED_DOCS.items():
        doc_path = ROOT / 'docs' / 'platform-contracts' / f'{slug}.md'
        doc_errors, doc_warnings = check_doc(
            doc_path,
            title,
            max_age_days=args.max_age_days,
            stale_policy=args.stale_policy,
        )
        errors += doc_errors
        warnings += doc_warnings

    if errors:
        return 1
    print(f'OK: verified {len(REQUIRED_DOCS)} platform contract document(s) ({warnings} warning(s))')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
