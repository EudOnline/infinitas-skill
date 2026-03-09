#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

from release_lib import ROOT, ReleaseError, signer_entries, signing_key_path


class AttestationError(Exception):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_attestation_config(root=None):
    root = Path(root or ROOT).resolve()
    config = load_json(root / 'config' / 'signing.json')
    git_tag = config.get('git_tag') if isinstance(config.get('git_tag'), dict) else {}
    attestation = config.get('attestation') if isinstance(config.get('attestation'), dict) else {}
    policy = attestation.get('policy') if isinstance(attestation.get('policy'), dict) else {}
    mode = policy.get('mode', 'enforce')
    allowed_rel = attestation.get('allowed_signers') or config.get('allowed_signers') or 'config/allowed_signers'
    namespace = attestation.get('namespace') or config.get('namespace') or 'infinitas-skill'
    signature_ext = attestation.get('signature_ext') or config.get('signature_ext') or '.ssig'
    return {
        'config': config,
        'format': attestation.get('format', 'ssh'),
        'namespace': namespace,
        'allowed_signers_rel': allowed_rel,
        'allowed_signers_path': (root / allowed_rel).resolve(),
        'signature_ext': signature_ext,
        'signing_key_env': attestation.get('signing_key_env') or git_tag.get('signing_key_env') or 'INFINITAS_SKILL_GIT_SIGNING_KEY',
        'policy_mode': mode,
        'require_release_output': bool(
            policy.get('require_verified_attestation_for_release_output', mode == 'enforce')
        ),
        'require_distribution': bool(
            policy.get('require_verified_attestation_for_distribution', mode == 'enforce')
        ),
    }


def signature_path_for(provenance_path, config=None):
    path = Path(provenance_path)
    cfg = config or load_attestation_config(path.parent.parent.parent if path.name else ROOT)
    return path.with_suffix(path.suffix + cfg['signature_ext'])


def require_trusted_signers(config):
    entries = signer_entries(config['allowed_signers_path'])
    if not entries:
        raise AttestationError(
            f"{config['allowed_signers_rel']} has no signer entries; add trusted release signers before writing or verifying stable attestations"
        )
    return entries


def resolve_attestation_signer(identity=None, release_state=None):
    signer = identity
    if not signer and release_state:
        signer = ((release_state.get('git') or {}).get('local_tag') or {}).get('signer')
    if not signer:
        raise AttestationError(
            'cannot determine attestation signer identity; pass --signer or verify the release tag against repo-managed allowed signers first'
        )
    return signer


def resolve_attestation_key(root=None, config=None, override=None):
    if override:
        return override
    root = Path(root or ROOT).resolve()
    cfg = config or load_attestation_config(root)
    value = signing_key_path(root, {'signing_key_env': cfg['signing_key_env']})
    if not value:
        raise AttestationError(
            f"stable release attestations require an SSH signing key; set {cfg['signing_key_env']} or git config user.signingkey"
        )
    return value


def validate_provenance_payload(payload):
    errors = []

    def require_string(mapping, key, label):
        value = mapping.get(key) if isinstance(mapping, dict) else None
        if not isinstance(value, str) or not value.strip():
            errors.append(f'{label} must be a non-empty string')
        return value

    if payload.get('kind') != 'skill-release-attestation':
        errors.append('kind must be skill-release-attestation')
    if payload.get('schema_version') != 1:
        errors.append('schema_version must be 1')

    skill = payload.get('skill')
    if not isinstance(skill, dict):
        errors.append('skill must be an object')
    else:
        require_string(skill, 'name', 'skill.name')
        require_string(skill, 'version', 'skill.version')
        require_string(skill, 'path', 'skill.path')

    git = payload.get('git')
    if not isinstance(git, dict):
        errors.append('git must be an object')
    else:
        require_string(git, 'commit', 'git.commit')
        require_string(git, 'expected_tag', 'git.expected_tag')
        require_string(git, 'release_ref', 'git.release_ref')
        if git.get('signed_tag_verified') is not True:
            errors.append('git.signed_tag_verified must be true')

    source_snapshot = payload.get('source_snapshot')
    if not isinstance(source_snapshot, dict):
        errors.append('source_snapshot must be an object')
    else:
        require_string(source_snapshot, 'tag', 'source_snapshot.tag')
        require_string(source_snapshot, 'ref', 'source_snapshot.ref')
        require_string(source_snapshot, 'commit', 'source_snapshot.commit')
        if source_snapshot.get('immutable') is not True:
            errors.append('source_snapshot.immutable must be true')
        if source_snapshot.get('pushed') is not True:
            errors.append('source_snapshot.pushed must be true')

    registry = payload.get('registry')
    if not isinstance(registry, dict):
        errors.append('registry must be an object')
    else:
        if not isinstance(registry.get('registries_consulted'), list):
            errors.append('registry.registries_consulted must be an array')
        if not isinstance(registry.get('resolved'), list):
            errors.append('registry.resolved must be an array')

    dependencies = payload.get('dependencies')
    if not isinstance(dependencies, dict):
        errors.append('dependencies must be an object')
    else:
        if not isinstance(dependencies.get('steps'), list):
            errors.append('dependencies.steps must be an array')
        if not isinstance(dependencies.get('registries_consulted'), list):
            errors.append('dependencies.registries_consulted must be an array')

    attestation = payload.get('attestation')
    if not isinstance(attestation, dict):
        errors.append('attestation must be an object')
    else:
        if attestation.get('format') != 'ssh':
            errors.append('attestation.format must be ssh')
        require_string(attestation, 'namespace', 'attestation.namespace')
        require_string(attestation, 'allowed_signers', 'attestation.allowed_signers')
        require_string(attestation, 'signature_file', 'attestation.signature_file')
        require_string(attestation, 'signature_ext', 'attestation.signature_ext')
        require_string(attestation, 'signer_identity', 'attestation.signer_identity')
        if attestation.get('policy_mode') not in {'advisory', 'enforce'}:
            errors.append('attestation.policy_mode must be advisory or enforce')
        if not isinstance(attestation.get('require_verified_attestation_for_release_output'), bool):
            errors.append('attestation.require_verified_attestation_for_release_output must be boolean')
        if not isinstance(attestation.get('require_verified_attestation_for_distribution'), bool):
            errors.append('attestation.require_verified_attestation_for_distribution must be boolean')

    return errors


def _combined_output(result):
    parts = []
    if result.stdout:
        parts.append(result.stdout.strip())
    if result.stderr:
        parts.append(result.stderr.strip())
    return '\n'.join(part for part in parts if part).strip()


def verify_attestation(provenance_path, identity=None, allowed_signers=None, namespace=None, root=None):
    root = Path(root or ROOT).resolve()
    provenance_path = Path(provenance_path).resolve()
    try:
        payload = load_json(provenance_path)
    except Exception as exc:
        raise AttestationError(f'could not parse attestation payload {provenance_path}: {exc}') from exc

    errors = validate_provenance_payload(payload)
    if errors:
        raise AttestationError('; '.join(errors))

    cfg = load_attestation_config(root)
    attestation = payload['attestation']
    identity = identity or attestation.get('signer_identity')
    expected_allowed_rel = cfg['allowed_signers_rel']
    expected_namespace = cfg['namespace']
    if allowed_signers:
        allowed_path = Path(allowed_signers)
        if not allowed_path.is_absolute():
            allowed_path = (root / allowed_path).resolve()
    else:
        if attestation.get('allowed_signers') != expected_allowed_rel:
            raise AttestationError(
                f"attestation allowed_signers {attestation.get('allowed_signers')!r} does not match repo-managed {expected_allowed_rel!r}"
            )
        allowed_path = cfg['allowed_signers_path']
    if namespace:
        verify_namespace = namespace
    else:
        if attestation.get('namespace') != expected_namespace:
            raise AttestationError(
                f"attestation namespace {attestation.get('namespace')!r} does not match repo-managed {expected_namespace!r}"
            )
        verify_namespace = expected_namespace

    require_trusted_signers({
        'allowed_signers_rel': str(allowed_path.relative_to(root)) if allowed_path.is_relative_to(root) else str(allowed_path),
        'allowed_signers_path': allowed_path,
    })

    signature_file = attestation.get('signature_file')
    signature_path = Path(signature_file)
    if not signature_path.is_absolute():
        signature_path = (provenance_path.parent / signature_path).resolve()
    if not signature_path.exists():
        raise AttestationError(f'missing SSH attestation signature: {signature_path}')

    result = subprocess.run(
        [
            'ssh-keygen',
            '-Y',
            'verify',
            '-f',
            str(allowed_path),
            '-I',
            identity,
            '-n',
            verify_namespace,
            '-s',
            str(signature_path),
        ],
        input=provenance_path.read_text(encoding='utf-8'),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AttestationError(_combined_output(result) or 'SSH attestation verification failed')
    return {
        'verified': True,
        'skill': payload.get('skill', {}).get('name'),
        'version': payload.get('skill', {}).get('version'),
        'identity': identity,
        'namespace': verify_namespace,
        'allowed_signers': str(allowed_path),
        'signature_path': str(signature_path),
        'output': _combined_output(result),
    }
