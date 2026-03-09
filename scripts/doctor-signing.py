#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from attestation_lib import AttestationError, load_attestation_config, verify_attestation
from release_lib import (
    ROOT,
    ReleaseError,
    collect_release_state,
    load_signing_config,
    resolve_releaser_identity,
    resolve_skill,
    signer_entries,
    signing_key_path,
)
from signing_bootstrap_lib import (
    SigningBootstrapError,
    normalize_public_key,
    parse_allowed_signers,
    public_key_from_key_path,
    signer_identities_for_key,
)


def parse_args():
    parser = argparse.ArgumentParser(description='Diagnose SSH signing bootstrap, release-tag readiness, and attestation prerequisites')
    parser.add_argument('skill', nargs='?', help='Skill name or path to diagnose')
    parser.add_argument('--identity', help='Expected signer identity to use in fix suggestions')
    parser.add_argument('--provenance', help='Existing provenance JSON to verify')
    parser.add_argument('--json', action='store_true', help='Print machine-readable doctor output')
    return parser.parse_args()


def make_check(check_id, status, summary, *, detail=None, fixes=None, data=None):
    return {
        'id': check_id,
        'status': status,
        'summary': summary,
        'detail': detail,
        'fixes': fixes or [],
        'data': data or {},
    }


def summarize_overall(checks):
    statuses = [check['status'] for check in checks]
    if 'fail' in statuses:
        return 'fail'
    if 'warn' in statuses:
        return 'warn'
    return 'ok'


def release_fix_suggestions(error, skill_name, branch=None):
    fixes = []
    if 'worktree is dirty' in error:
        fixes.append('Commit or stash local changes, then rerun `python3 scripts/doctor-signing.py ' + skill_name + '`')
    elif 'has no upstream' in error:
        current_branch = branch or 'main'
        fixes.append(f'Set an upstream with `git push -u origin {current_branch}`')
    elif 'ahead of' in error:
        fixes.append('Push the current branch so release checks and the release tag point at the same commit')
    elif 'behind' in error:
        fixes.append('Fast-forward from upstream before tagging, for example `git pull --ff-only`')
    elif 'publisher' in error or 'namespace transfer' in error:
        fixes.append('Update `policy/namespace-policy.json`, then rerun `scripts/check-all.sh`')
    elif 'expected release tag is missing' in error:
        fixes.append(f'Create and push the release tag with `scripts/release-skill.sh {skill_name} --push-tag`')
    elif 'not pushed to' in error:
        fixes.append(f'Push the release tag with `scripts/release-skill.sh {skill_name} --push-tag` or `git push origin refs/tags/...`')
    elif 'did not verify against repo-managed signers' in error:
        fixes.append('Ensure the configured SSH signing key is committed in `config/allowed_signers` and matches the release tag signer')
    return fixes


def render_human(report):
    print('doctor: signing bootstrap and release readiness')
    print(f'overall: {report["overall_status"].upper()}')
    for check in report['checks']:
        print()
        print(f'[{check["status"].upper()}] {check["id"]}: {check["summary"]}')
        if check.get('detail'):
            print(f'  detail: {check["detail"]}')
        for fix in check.get('fixes') or []:
            print(f'  fix: {fix}')


def main():
    args = parse_args()
    checks = []
    skill_dir = None
    skill_state = None
    skill_name = args.skill or '<skill>'
    inferred_signer_identities = []
    expected_provenance = None

    try:
        signing = load_signing_config(ROOT)
        attestation = load_attestation_config(ROOT)
    except Exception as exc:
        report = {'overall_status': 'fail', 'checks': [make_check('signing-config', 'fail', 'Cannot load signing configuration', detail=str(exc))]}
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            render_human(report)
        raise SystemExit(1)

    try:
        allowed_entries = parse_allowed_signers(signing['allowed_signers_path'])
    except SigningBootstrapError as exc:
        allowed_entries = []
        checks.append(
            make_check(
                'allowed-signers-format',
                'fail',
                f'{signing["allowed_signers_rel"]} is malformed',
                detail=str(exc),
                fixes=[f'Fix the malformed line in `{signing["allowed_signers_rel"]}` and rerun `scripts/check-all.sh`'],
            )
        )
    else:
        if not allowed_entries:
            identity_hint = args.identity or 'release-signer'
            checks.append(
                make_check(
                    'trusted-signers',
                    'fail',
                    f'{signing["allowed_signers_rel"]} has no trusted signer entries',
                    detail='Stable tag verification and release attestation verification remain blocked until at least one trusted public key is committed.',
                    fixes=[
                        f'Generate or reuse a key, then run `python3 scripts/bootstrap-signing.py add-allowed-signer --identity {identity_hint} --key ~/.ssh/id_ed25519`',
                        'Commit and push the updated `config/allowed_signers` before creating the first stable tag',
                    ],
                )
            )
        else:
            checks.append(
                make_check(
                    'trusted-signers',
                    'ok',
                    f'{signing["allowed_signers_rel"]} contains {len(allowed_entries)} trusted signer entr' + ('y' if len(allowed_entries) == 1 else 'ies'),
                    detail='Committed signer identities are available for tag and attestation verification.',
                    data={'identities': [entry['identity'] for entry in allowed_entries]},
                )
            )

    configured_key = signing_key_path(ROOT, signing)
    if not configured_key:
        identity_hint = args.identity or 'release-signer'
        checks.append(
            make_check(
                'signing-key',
                'fail',
                'No SSH signing key is configured for stable release tags',
                detail=f'Set `{signing["signing_key_env"]}` or `git config user.signingkey` to a private SSH key path.',
                fixes=[
                    f'Create a key with `python3 scripts/bootstrap-signing.py init-key --identity {identity_hint} --output ~/.ssh/infinitas-skill-release-signing`',
                    'Point git at that key with `python3 scripts/bootstrap-signing.py configure-git --key ~/.ssh/infinitas-skill-release-signing`',
                ],
            )
        )
    else:
        key_path = Path(configured_key).expanduser()
        if not key_path.exists():
            checks.append(
                make_check(
                    'signing-key',
                    'fail',
                    f'Configured SSH signing key does not exist: {key_path}',
                    detail='Release tag creation cannot succeed until the configured private key path is present.',
                    fixes=['Update the key path in git config or recreate the key with `python3 scripts/bootstrap-signing.py init-key ...`'],
                )
            )
        else:
            try:
                configured_public_key = public_key_from_key_path(key_path)
            except SigningBootstrapError as exc:
                checks.append(make_check('signing-key', 'fail', 'Cannot read configured SSH signing key', detail=str(exc)))
                configured_public_key = None
            else:
                inferred_signer_identities = signer_identities_for_key(allowed_entries, configured_public_key)
                if allowed_entries and not inferred_signer_identities:
                    identity_hint = args.identity or 'release-signer'
                    checks.append(
                        make_check(
                            'signing-key-trust',
                            'fail',
                            'Configured SSH signing key is not trusted by the repository',
                            detail=f'The key at `{key_path}` is not present in `{signing["allowed_signers_rel"]}`.',
                            fixes=[
                                f'Run `python3 scripts/bootstrap-signing.py add-allowed-signer --identity {identity_hint} --key {key_path}`',
                                f'Commit and push the updated `{signing["allowed_signers_rel"]}` before tagging',
                            ],
                        )
                    )
                else:
                    detail = f'Configured key path: {key_path}'
                    if inferred_signer_identities:
                        detail += '; matched identities: ' + ', '.join(inferred_signer_identities)
                    checks.append(make_check('signing-key', 'ok', 'An SSH signing key is configured for release tags', detail=detail))

    gpg_format = __import__('subprocess').run(
        ['git', 'config', '--get', 'gpg.format'],
        cwd=ROOT,
        text=True,
        capture_output=True,
    ).stdout.strip()
    if gpg_format and gpg_format != 'ssh':
        checks.append(
            make_check(
                'git-gpg-format',
                'warn',
                f'git config gpg.format is {gpg_format!r}, not ssh',
                detail='Release helpers override this automatically, but setting `ssh` keeps manual git tag signing consistent.',
                fixes=['Run `python3 scripts/bootstrap-signing.py configure-git --key <private-key>` to normalize local git config'],
            )
        )
    else:
        checks.append(
            make_check(
                'git-gpg-format',
                'ok',
                'Git SSH signing format is configured or will be injected by release helpers',
                detail='Manual `git tag -s` use is simplest when `gpg.format=ssh`.',
            )
        )

    if args.skill:
        try:
            skill_dir = resolve_skill(ROOT, args.skill)
            skill_name = skill_dir.name
            skill_state = collect_release_state(skill_dir, mode='preflight')
        except ReleaseError as exc:
            checks.append(make_check('release-preflight', 'fail', f'Cannot resolve release state for {args.skill}', detail=str(exc)))
        else:
            branch = ((skill_state.get('git') or {}).get('branch') or '').strip() or None
            skill = skill_state.get('skill') or {}
            expected_provenance = ROOT / 'catalog' / 'provenance' / f"{skill.get('name')}-{skill.get('version')}.json"
            has_provenance_artifact = False
            if args.provenance:
                has_provenance_artifact = Path(args.provenance).expanduser().resolve().exists()
            elif expected_provenance:
                has_provenance_artifact = expected_provenance.exists()
            preflight_errors = skill_state.get('errors') or []
            if preflight_errors:
                dirty_only = (
                    len(preflight_errors) == 1
                    and 'worktree is dirty' in preflight_errors[0]
                    and has_provenance_artifact
                )
                fixes = []
                for error in preflight_errors:
                    fixes.extend(release_fix_suggestions(error, skill_name, branch=branch))
                checks.append(
                    make_check(
                        'release-preflight',
                        'warn' if dirty_only else 'fail',
                        (
                            f'Release preflight for {skill_name} is dirty after writing release artifacts'
                            if dirty_only
                            else f'Release preflight is blocked for {skill_name}'
                        ),
                        detail=(
                            'Current tag and attestation can verify, but you should commit or clean generated release artifacts before the next stable release.'
                            if dirty_only
                            else '; '.join(preflight_errors)
                        ),
                        fixes=list(
                            dict.fromkeys(
                                fixes
                                or ['Commit generated provenance or clean the worktree before the next stable release']
                            )
                        ),
                        data={'errors': preflight_errors},
                    )
                )
            else:
                checks.append(
                    make_check(
                        'release-preflight',
                        'ok',
                        f'Release preflight is clean for {skill_name}',
                        detail='Worktree, upstream sync, and namespace policy checks are ready for signed tag creation.',
                    )
                )

            if skill_state:
                release = skill_state.get('release') or {}
                publisher = skill.get('publisher')
                if publisher and inferred_signer_identities and release.get('authorized_signers'):
                    unauthorized = [identity for identity in inferred_signer_identities if identity not in release.get('authorized_signers', [])]
                    if unauthorized:
                        checks.append(
                            make_check(
                                'namespace-signer-policy',
                                'warn',
                                f'Configured signer identities are not authorized for publisher {publisher}',
                                detail='Current matches: ' + ', '.join(unauthorized),
                                fixes=[
                                    'Authorize them with `python3 scripts/bootstrap-signing.py authorize-publisher --publisher '
                                    + publisher
                                    + ' '
                                    + ' '.join(f'--signer {identity}' for identity in unauthorized)
                                    + '`'
                                ],
                            )
                        )
                    else:
                        checks.append(
                            make_check(
                                'namespace-signer-policy',
                                'ok',
                                f'Configured signer identity is authorized for publisher {publisher}',
                            )
                        )
                releaser_identity = resolve_releaser_identity(ROOT)
                authorized_releasers = release.get('authorized_releasers') or []
                if publisher and releaser_identity and authorized_releasers and releaser_identity not in authorized_releasers:
                    checks.append(
                        make_check(
                            'namespace-releaser-policy',
                            'warn',
                            f'Releaser identity {releaser_identity!r} is not authorized for publisher {publisher}',
                            detail='Release output still works today, but audit warnings will remain until policy is updated.',
                            fixes=[
                                f'Run `python3 scripts/bootstrap-signing.py authorize-publisher --publisher {publisher} --releaser {json.dumps(releaser_identity)}`'
                            ],
                        )
                    )
                elif publisher and releaser_identity and authorized_releasers:
                    checks.append(
                        make_check(
                            'namespace-releaser-policy',
                            'ok',
                            f'Releaser identity {releaser_identity!r} is authorized for publisher {publisher}',
                        )
                    )

                tag_state = (skill_state.get('git') or {}).get('local_tag') or {}
                if not tag_state.get('exists'):
                    checks.append(
                        make_check(
                            'release-tag',
                            'info',
                            f'No local signed release tag exists yet for {skill_state["git"]["expected_tag"]}',
                            detail='Tag signing is ready once the bootstrap checks above are green.',
                            fixes=[f'Create and push the first stable tag with `scripts/release-skill.sh {skill_name} --push-tag`'],
                        )
                    )
                elif tag_state.get('verified'):
                    remote_tag = (skill_state.get('git') or {}).get('remote_tag') or {}
                    if remote_tag.get('tag_exists'):
                        checks.append(
                            make_check(
                                'release-tag',
                                'ok',
                                f'Release tag {skill_state["git"]["expected_tag"]} is signed and pushed',
                                detail='Repo-managed SSH signers verify the current stable tag.',
                            )
                        )
                    else:
                        checks.append(
                            make_check(
                                'release-tag',
                                'info',
                                f'Release tag {skill_state["git"]["expected_tag"]} is signed locally but not pushed yet',
                                fixes=[f'Push it with `scripts/release-skill.sh {skill_name} --push-tag`'],
                            )
                        )
                else:
                    detail = tag_state.get('verification_error') or 'Tag exists but verification failed'
                    checks.append(
                        make_check(
                            'release-tag',
                            'fail',
                            f'Release tag {skill_state["git"]["expected_tag"]} is present but not verified',
                            detail=detail,
                            fixes=[f'Recreate it with `scripts/release-skill-tag.sh {skill_name} --create --force` after fixing the signer bootstrap'],
                        )
                    )

    provenance_path = Path(args.provenance).resolve() if args.provenance else expected_provenance
    if provenance_path:
        if provenance_path.exists():
            try:
                verified = verify_attestation(str(provenance_path), identity=args.identity)
            except AttestationError as exc:
                checks.append(
                    make_check(
                        'attestation',
                        'fail',
                        f'Attestation verification failed for {provenance_path}',
                        detail=str(exc),
                        fixes=['Repair the signing bootstrap or regenerate provenance with `scripts/release-skill.sh <skill> --write-provenance`'],
                    )
                )
            else:
                checks.append(
                    make_check(
                        'attestation',
                        'ok',
                        f'Attestation verifies for {provenance_path.name}',
                        detail=f"signer={verified['identity']} namespace={verified['namespace']}",
                    )
                )
        elif args.provenance:
            checks.append(
                make_check(
                    'attestation',
                    'fail',
                    f'Provenance file does not exist: {provenance_path}',
                    detail='Doctor cannot verify an attestation bundle until the JSON payload exists.',
                    fixes=['Create it with `scripts/release-skill.sh <skill> --write-provenance`'],
                )
            )
        else:
            checks.append(
                make_check(
                    'attestation',
                    'info',
                    f'No attestation bundle exists yet at {provenance_path}',
                    detail='Attestation verification will become available immediately after the first stable release writes provenance.',
                    fixes=['Write it with `scripts/release-skill.sh <skill> --notes-out /tmp/<skill>-release.md --write-provenance`'],
                )
            )

    report = {
        'overall_status': summarize_overall(checks),
        'skill': str(skill_dir.relative_to(ROOT)) if skill_dir else None,
        'expected_provenance': str(provenance_path.relative_to(ROOT)) if provenance_path and provenance_path.is_relative_to(ROOT) else (str(provenance_path) if provenance_path else None),
        'inferred_signer_identities': inferred_signer_identities,
        'checks': checks,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render_human(report)
    if report['overall_status'] == 'fail':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
