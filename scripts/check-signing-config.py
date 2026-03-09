#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SIGNING_PATH = ROOT / 'config' / 'signing.json'


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def resolve_relative(path_value):
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def validate_allowed_signers(path_value, label, errors, warnings):
    if not is_nonempty_string(path_value):
        errors.append(f'{label} must be a non-empty string path')
        return None
    path = resolve_relative(path_value)
    if not path.exists():
        errors.append(f'{label} does not exist: {path}')
        return path
    trusted = 0
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            errors.append(f'{label} line {number} must use "<identity> <public-key>" format')
            continue
        if not parts[0].strip():
            errors.append(f'{label} line {number} has an empty identity')
            continue
        trusted += 1
    if trusted == 0:
        warnings.append(
            f'{path_value} has no trusted signer entries yet; stable tag and attestation verification stay blocked until it is populated'
        )
    return path


def main():
    errors = []
    warnings = []
    if not SIGNING_PATH.exists():
        print(f'FAIL: missing signing config: {SIGNING_PATH}', file=sys.stderr)
        raise SystemExit(1)

    try:
        config = load_json(SIGNING_PATH)
    except Exception as exc:
        print(f'FAIL: could not parse {SIGNING_PATH}: {exc}', file=sys.stderr)
        raise SystemExit(1)

    top_namespace = config.get('namespace')
    top_allowed = config.get('allowed_signers')
    top_ext = config.get('signature_ext')
    git_tag = config.get('git_tag') if isinstance(config.get('git_tag'), dict) else {}
    attestation = config.get('attestation') if isinstance(config.get('attestation'), dict) else {}
    policy = attestation.get('policy') if isinstance(attestation.get('policy'), dict) else {}

    if not is_nonempty_string(top_namespace):
        errors.append('namespace must be a non-empty string')
    if not is_nonempty_string(top_allowed):
        errors.append('allowed_signers must be a non-empty string path')
    if not is_nonempty_string(top_ext) or not top_ext.startswith('.'):
        errors.append('signature_ext must be a non-empty extension starting with "."')

    if git_tag.get('format') != 'ssh':
        errors.append('git_tag.format must be ssh for the v9 release policy')
    if not is_nonempty_string(git_tag.get('allowed_signers')):
        errors.append('git_tag.allowed_signers must be a non-empty string path')
    if not is_nonempty_string(git_tag.get('remote')):
        errors.append('git_tag.remote must be a non-empty string')
    if not is_nonempty_string(git_tag.get('signing_key_env')):
        errors.append('git_tag.signing_key_env must be a non-empty string')

    if attestation.get('format') != 'ssh':
        errors.append('attestation.format must be ssh')
    if not is_nonempty_string(attestation.get('namespace')):
        errors.append('attestation.namespace must be a non-empty string')
    if not is_nonempty_string(attestation.get('allowed_signers')):
        errors.append('attestation.allowed_signers must be a non-empty string path')
    if not is_nonempty_string(attestation.get('signature_ext')) or not attestation.get('signature_ext', '').startswith('.'):
        errors.append('attestation.signature_ext must be a non-empty extension starting with "."')
    if not is_nonempty_string(attestation.get('signing_key_env')):
        errors.append('attestation.signing_key_env must be a non-empty string')
    if policy.get('mode') not in {'advisory', 'enforce'}:
        errors.append('attestation.policy.mode must be advisory or enforce')
    for key in [
        'require_verified_attestation_for_release_output',
        'require_verified_attestation_for_distribution',
    ]:
        if not isinstance(policy.get(key), bool):
            errors.append(f'attestation.policy.{key} must be boolean')

    top_allowed_path = validate_allowed_signers(top_allowed, 'allowed_signers', errors, warnings) if top_allowed else None
    git_tag_allowed_path = validate_allowed_signers(git_tag.get('allowed_signers'), 'git_tag.allowed_signers', errors, warnings) if git_tag.get('allowed_signers') else None
    attestation_allowed_path = validate_allowed_signers(attestation.get('allowed_signers'), 'attestation.allowed_signers', errors, warnings) if attestation.get('allowed_signers') else None

    if top_allowed_path and git_tag_allowed_path and top_allowed_path != git_tag_allowed_path:
        errors.append('git_tag.allowed_signers must resolve to the same path as allowed_signers')
    if top_allowed_path and attestation_allowed_path and top_allowed_path != attestation_allowed_path:
        errors.append('attestation.allowed_signers must resolve to the same path as allowed_signers')
    if is_nonempty_string(attestation.get('namespace')) and is_nonempty_string(top_namespace) and attestation.get('namespace') != top_namespace:
        errors.append('attestation.namespace must match namespace')
    if is_nonempty_string(attestation.get('signature_ext')) and is_nonempty_string(top_ext) and attestation.get('signature_ext') != top_ext:
        errors.append('attestation.signature_ext must match signature_ext')

    warnings = list(dict.fromkeys(warnings))
    for warning in warnings:
        print(f'WARN: {warning}', file=sys.stderr)
    if errors:
        for error in errors:
            print(f'FAIL: {error}', file=sys.stderr)
        raise SystemExit(1)
    print(f'OK: signing config checked ({len(warnings)} warning(s))')


if __name__ == '__main__':
    main()
