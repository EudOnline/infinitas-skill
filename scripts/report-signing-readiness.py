#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from attestation_lib import AttestationError, verify_attestation
from release_lib import (
    ROOT,
    ReleaseError,
    collect_release_state,
    load_signing_config,
    resolve_skill,
    signing_key_path,
)
from signing_bootstrap_lib import (
    SigningBootstrapError,
    parse_allowed_signers,
    public_key_from_key_path,
    signer_identities_for_key,
)


def parse_args():
    parser = argparse.ArgumentParser(description='Report repository-level SSH signing readiness')
    parser.add_argument(
        '--skill',
        action='append',
        default=[],
        help='Skill name or path to inspect (repeatable, defaults to all active skills)',
    )
    parser.add_argument('--json', action='store_true', help='Print machine-readable output')
    return parser.parse_args()


def status_from(findings):
    if findings.get('errors'):
        return 'fail'
    if findings.get('warnings'):
        return 'warn'
    return 'ok'


def ensure_skill_targets(root, requested):
    if requested:
        return requested
    active_root = root / 'skills' / 'active'
    if not active_root.is_dir():
        return []
    return [path.name for path in sorted(active_root.iterdir()) if path.is_dir() and (path / '_meta.json').exists()]


def summarize_trusted_signers(signing):
    warnings = []
    errors = []
    try:
        entries = parse_allowed_signers(signing['allowed_signers_path'])
    except SigningBootstrapError as exc:
        entries = []
        errors.append(str(exc))
    if not entries:
        warnings.append('no trusted signer entries are committed yet')
    identities = []
    for entry in entries:
        identity = entry.get('identity')
        if identity and identity not in identities:
            identities.append(identity)
    summary = {
        'status': 'ok' if entries else ('fail' if errors else 'warn'),
        'path': signing['allowed_signers_rel'],
        'count': len(entries),
        'identities': identities,
        'warnings': warnings,
        'errors': errors,
    }
    return entries, summary


def summarize_signing_key(root, signing, allowed_entries):
    warnings = []
    errors = []
    key_value = signing_key_path(root, signing)
    key_path = Path(key_value).expanduser() if key_value else None
    exists = bool(key_path and key_path.exists())
    matched_identities = []

    if not key_value:
        warnings.append('no SSH signing key is configured')
    elif not exists:
        warnings.append(f'configured SSH signing key does not exist: {key_path}')
    else:
        try:
            public_key = public_key_from_key_path(key_path)
        except SigningBootstrapError as exc:
            errors.append(str(exc))
        else:
            matched_identities = signer_identities_for_key(allowed_entries, public_key)
            if allowed_entries and not matched_identities:
                warnings.append('configured SSH signing key is not trusted by config/allowed_signers')

    findings = {'warnings': warnings, 'errors': errors}
    return {
        'status': status_from(findings),
        'configured': bool(key_value),
        'path': str(key_path) if key_path else None,
        'exists': exists,
        'trusted': bool(matched_identities),
        'matched_identities': matched_identities,
        'warnings': warnings,
        'errors': errors,
    }


def summarize_provenance(provenance_path):
    if not provenance_path.exists():
        return {
            'path': str(provenance_path),
            'present': False,
            'verified': False,
            'status': 'warn',
            'warnings': ['release provenance has not been generated yet'],
            'errors': [],
        }
    try:
        result = verify_attestation(provenance_path, root=ROOT)
    except AttestationError as exc:
        return {
            'path': str(provenance_path),
            'present': True,
            'verified': False,
            'status': 'fail',
            'signer_identity': None,
            'formats_verified': [],
            'warnings': [],
            'errors': [str(exc)],
        }
    return {
        'path': str(provenance_path),
        'present': True,
        'verified': True,
        'status': 'ok',
        'signer_identity': result.get('identity'),
        'formats_verified': result.get('formats_verified', []),
        'warnings': [],
        'errors': [],
    }


def summarize_skill(root, target):
    try:
        skill_dir = resolve_skill(root, target)
    except ReleaseError as exc:
        return {
            'name': target,
            'status': 'fail',
            'release_ready': False,
            'tag': {'present': False, 'verified': False},
            'provenance': {'present': False, 'verified': False},
            'warnings': [],
            'errors': [str(exc)],
        }

    state = collect_release_state(skill_dir, mode='local-tag', root=root)
    skill = state['skill']
    provenance_path = root / 'catalog' / 'provenance' / f"{skill['name']}-{skill['version']}.json"
    provenance = summarize_provenance(provenance_path)
    local_tag = (state.get('git') or {}).get('local_tag') or {}
    release = state.get('release') or {}

    signer_identity = local_tag.get('signer')
    authorized_signers = release.get('authorized_signers') or []
    authorized_releasers = release.get('authorized_releasers') or []
    releaser_identity = release.get('releaser_identity')

    signer_authorized = bool(signer_identity) and (
        not authorized_signers or signer_identity in authorized_signers
    )
    releaser_authorized = bool(releaser_identity) and (
        not authorized_releasers or releaser_identity in authorized_releasers
    )

    warnings = []
    errors = []

    if not local_tag.get('exists'):
        warnings.append('stable release tag is missing')
    elif not local_tag.get('verified'):
        errors.append(local_tag.get('verification_error') or 'stable release tag did not verify')

    if provenance.get('status') == 'warn':
        warnings.extend(provenance.get('warnings') or [])
    elif provenance.get('status') == 'fail':
        errors.extend(provenance.get('errors') or [])

    if authorized_signers and not signer_authorized:
        warnings.append('release tag signer is not authorized by namespace policy')
    if authorized_releasers and not releaser_authorized:
        warnings.append('resolved releaser identity is not authorized by namespace policy')

    findings = {'warnings': warnings, 'errors': errors}
    return {
        'name': skill.get('name'),
        'publisher': skill.get('publisher'),
        'qualified_name': skill.get('qualified_name'),
        'version': skill.get('version'),
        'path': skill.get('path'),
        'status': status_from(findings),
        'release_ready': not warnings and not errors,
        'tag': {
            'name': (state.get('git') or {}).get('expected_tag'),
            'present': bool(local_tag.get('exists')),
            'verified': bool(local_tag.get('verified')),
            'signed': bool(local_tag.get('signed')),
            'points_to_head': bool(local_tag.get('points_to_head')),
            'signer_identity': signer_identity,
        },
        'provenance': provenance,
        'policy': {
            'authorized_signers': authorized_signers,
            'authorized_releasers': authorized_releasers,
            'signer_authorized': signer_authorized,
            'releaser_identity': releaser_identity,
            'releaser_authorized': releaser_authorized,
        },
        'warnings': warnings,
        'errors': errors,
    }


def build_report(root, skill_targets):
    signing = load_signing_config(root)
    allowed_entries, trusted_signers = summarize_trusted_signers(signing)
    signing_key = summarize_signing_key(root, signing, allowed_entries)
    skills = [summarize_skill(root, target) for target in skill_targets]

    errors = []
    warnings = []

    if trusted_signers.get('status') == 'fail':
        errors.extend(trusted_signers.get('errors') or [])
    elif trusted_signers.get('status') == 'warn':
        warnings.extend(trusted_signers.get('warnings') or [])

    if signing_key.get('status') == 'fail':
        errors.extend(signing_key.get('errors') or [])
    elif signing_key.get('status') == 'warn':
        warnings.extend(signing_key.get('warnings') or [])

    for skill in skills:
        if skill.get('status') == 'fail':
            errors.extend(skill.get('errors') or [])
        elif skill.get('status') == 'warn':
            warnings.extend(skill.get('warnings') or [])

    overall_status = 'fail' if errors else ('warn' if warnings else 'ok')
    return {
        'overall_status': overall_status,
        'trusted_signers': trusted_signers,
        'signing_key': signing_key,
        'skills': skills,
    }


def render_human(report):
    print(f"overall: {report['overall_status'].upper()}")
    trusted = report.get('trusted_signers') or {}
    print(
        'trusted_signers: '
        f"{trusted.get('count', 0)}"
        + (
            f" ({', '.join(trusted.get('identities') or [])})"
            if trusted.get('identities')
            else ''
        )
    )
    signing_key = report.get('signing_key') or {}
    print(
        'signing_key: '
        + ('configured' if signing_key.get('configured') else 'missing')
        + (
            f" ({', '.join(signing_key.get('matched_identities') or [])})"
            if signing_key.get('matched_identities')
            else ''
        )
    )
    for skill in report.get('skills') or []:
        print()
        print(f"skill: {skill['name']} {skill['version']}")
        print(f"  status: {skill['status'].upper()}")
        print(f"  tag: present={skill['tag']['present']} verified={skill['tag']['verified']}")
        print(
            f"  provenance: present={skill['provenance']['present']} "
            f"verified={skill['provenance']['verified']}"
        )
        for warning in skill.get('warnings') or []:
            print(f'  warning: {warning}')
        for error in skill.get('errors') or []:
            print(f'  error: {error}')


def main():
    args = parse_args()
    skill_targets = ensure_skill_targets(ROOT, args.skill)
    report = build_report(ROOT, skill_targets)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render_human(report)
    raise SystemExit(1 if report['overall_status'] == 'fail' else 0)


if __name__ == '__main__':
    main()
