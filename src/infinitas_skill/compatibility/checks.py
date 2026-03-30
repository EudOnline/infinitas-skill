"""Platform compatibility checks and CLI helpers."""

import argparse
import sys
from datetime import date
from pathlib import Path

from infinitas_skill.compatibility.contracts import load_platform_profile_contract, validate_platform_contract
from infinitas_skill.legacy import ROOT

REQUIRED_PLATFORM_DOCS = {
    'claude': 'Claude Platform Contract',
    'codex': 'Codex Platform Contract',
    'openclaw': 'OpenClaw Platform Contract',
}
STALE_POLICIES = ('warn', 'fail')


def collect_platform_contract_result(
    path: Path,
    title: str,
    *,
    root: Path,
    max_age_days: int | None,
    stale_policy: str,
) -> dict:
    errors = []
    warnings = []
    payload, validation_errors = validate_platform_contract(path, title)
    errors.extend(validation_errors)

    profile_path = root / 'profiles' / f'{path.stem}.json'
    profile_payload, profile_errors = load_platform_profile_contract(profile_path, path.stem)
    errors.extend(profile_errors)

    doc_sources = payload.get('official_sources') or []
    profile_sources = profile_payload.get('sources') or []
    if doc_sources and profile_sources and profile_sources != doc_sources:
        errors.append(f'{profile_path}: contract.sources do not match {path}: {profile_sources!r} != {doc_sources!r}')

    verified_date = payload.get('last_verified')
    profile_last_verified = profile_payload.get('last_verified')
    if isinstance(verified_date, date) and profile_last_verified and profile_last_verified != verified_date.isoformat():
        errors.append(
            f'{profile_path}: contract.last_verified {profile_last_verified!r} does not match '
            f'{path} {verified_date.isoformat()!r}'
        )

    if isinstance(verified_date, date) and max_age_days is not None:
        age_days = (date.today() - verified_date).days
        if age_days > max_age_days:
            message = (
                f'{path}: last verified {verified_date.isoformat()} is {age_days} days old '
                f'(threshold {max_age_days})'
            )
            if stale_policy == 'fail':
                errors.append(message)
            else:
                warnings.append(message)

    return {
        'slug': path.stem,
        'doc_path': path,
        'profile_path': profile_path,
        'errors': errors,
        'warnings': warnings,
        'doc': payload,
        'profile': profile_payload,
    }


def collect_platform_contracts_report(
    *,
    max_age_days: int | None = None,
    stale_policy: str = 'warn',
    root: str | Path | None = None,
) -> dict:
    repo_root = Path(root or ROOT).resolve()
    results = []
    errors = []
    warnings = []

    for slug, title in REQUIRED_PLATFORM_DOCS.items():
        doc_path = repo_root / 'docs' / 'platform-contracts' / f'{slug}.md'
        result = collect_platform_contract_result(
            doc_path,
            title,
            root=repo_root,
            max_age_days=max_age_days,
            stale_policy=stale_policy,
        )
        results.append(result)
        errors.extend(result['errors'])
        warnings.extend(result['warnings'])

    return {
        'root': repo_root,
        'documents': results,
        'errors': errors,
        'warnings': warnings,
    }


def emit_platform_contracts_report(report: dict, *, stdout=None, stderr=None) -> None:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    for item in report.get('documents', []):
        for message in item.get('errors', []):
            print(f'FAIL: {message}', file=stderr)
        for message in item.get('warnings', []):
            print(f'WARN: {message}', file=stderr)


def configure_platform_contracts_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument(
        '--max-age-days',
        type=int,
        default=None,
        help='Warn when Last verified is older than this many days.',
    )
    parser.add_argument(
        '--stale-policy',
        choices=STALE_POLICIES,
        default='warn',
        help='Whether over-age contract docs should warn or fail.',
    )
    return parser


def build_platform_contracts_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description='Check platform contract-watch documents.')
    return configure_platform_contracts_parser(parser)


def parse_platform_contracts_args(
    argv: list[str] | None = None,
    *,
    prog: str | None = None,
) -> argparse.Namespace:
    return build_platform_contracts_parser(prog=prog).parse_args(argv)


def run_check_platform_contracts(
    *,
    max_age_days: int | None = None,
    stale_policy: str = 'warn',
    root: str | Path | None = None,
) -> int:
    report = collect_platform_contracts_report(
        max_age_days=max_age_days,
        stale_policy=stale_policy,
        root=root,
    )
    emit_platform_contracts_report(report)
    if report['errors']:
        return 1
    print(
        f'OK: verified {len(REQUIRED_PLATFORM_DOCS)} platform contract document(s) '
        f'({len(report["warnings"])} warning(s))'
    )
    return 0


def platform_contracts_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    args = parse_platform_contracts_args(argv, prog=prog)
    return run_check_platform_contracts(
        max_age_days=args.max_age_days,
        stale_policy=args.stale_policy,
    )


__all__ = [
    'REQUIRED_PLATFORM_DOCS',
    'STALE_POLICIES',
    'build_platform_contracts_parser',
    'collect_platform_contract_result',
    'collect_platform_contracts_report',
    'configure_platform_contracts_parser',
    'emit_platform_contracts_report',
    'parse_platform_contracts_args',
    'platform_contracts_main',
    'run_check_platform_contracts',
]
