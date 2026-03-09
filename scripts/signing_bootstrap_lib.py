#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

from release_lib import ROOT

KEY_PREFIXES = ('ssh-', 'ecdsa-', 'sk-')


class SigningBootstrapError(Exception):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_allowed_signers(path):
    entries = []
    path = Path(path)
    if not path.exists():
        return entries
    for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        parts = stripped.split(None, 1)
        if len(parts) < 2 or not parts[0].strip() or not normalize_public_key(parts[1]):
            raise SigningBootstrapError(
                f'{path} line {line_number} must use "<identity> <public-key>" format'
            )
        identity = parts[0].strip()
        public_key = parts[1].strip()
        entries.append(
            {
                'line_number': line_number,
                'identity': identity,
                'public_key': public_key,
                'normalized_key': normalize_public_key(public_key),
            }
        )
    return entries


def normalize_public_key(value):
    tokens = (value or '').strip().split()
    for index, token in enumerate(tokens):
        if token.startswith(KEY_PREFIXES):
            if index + 1 >= len(tokens):
                return None
            return f'{token} {tokens[index + 1]}'
    return None


def public_key_from_private_key(path):
    result = subprocess.run(
        ['ssh-keygen', '-y', '-f', str(path)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or 'ssh-keygen failed'
        raise SigningBootstrapError(f'cannot derive public key from {path}: {message}')
    return result.stdout.strip()


def public_key_from_file(path):
    text = Path(path).read_text(encoding='utf-8').strip()
    if not normalize_public_key(text):
        raise SigningBootstrapError(f'{path} does not contain a valid SSH public key')
    return text


def public_key_from_key_path(path):
    key_path = Path(path).expanduser()
    if not key_path.exists():
        raise SigningBootstrapError(f'key path does not exist: {key_path}')
    if key_path.suffix == '.pub':
        return public_key_from_file(key_path)
    return public_key_from_private_key(key_path)


def upsert_allowed_signer(path, identity, public_key):
    allowed_path = Path(path)
    existing_lines = allowed_path.read_text(encoding='utf-8').splitlines() if allowed_path.exists() else []
    desired_line = f'{identity} {public_key.strip()}'
    new_lines = []
    replaced = False
    changed = False
    matched_existing = False
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            new_lines.append(line)
            continue
        parts = stripped.split(None, 1)
        if len(parts) < 2:
            new_lines.append(line)
            continue
        if parts[0].strip() != identity:
            new_lines.append(line)
            continue
        matched_existing = True
        if not replaced:
            new_lines.append(desired_line)
            replaced = True
            if stripped != desired_line:
                changed = True
        else:
            changed = True
    if not matched_existing:
        if new_lines and new_lines[-1].strip():
            new_lines.append('')
        new_lines.append(desired_line)
        changed = True
    if changed:
        allowed_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
    return {
        'changed': changed,
        'action': 'updated' if matched_existing else 'added',
        'line': desired_line,
    }


def configure_git_signing(root, key_path, scope='local'):
    commands = [
        ['git', 'config', 'gpg.format', 'ssh'],
        ['git', 'config', 'user.signingkey', str(Path(key_path).expanduser())],
    ]
    if scope == 'global':
        commands = [command[:2] + ['--global'] + command[2:] for command in commands]
    for command in commands:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or 'git config failed'
            raise SigningBootstrapError(message)


def update_namespace_policy(path, publisher, *, signers=None, releasers=None):
    policy_path = Path(path)
    payload = load_json(policy_path)
    publishers = payload.get('publishers') if isinstance(payload.get('publishers'), dict) else {}
    if publisher not in publishers:
        raise SigningBootstrapError(f'publisher {publisher!r} is not declared in {policy_path}')
    entry = publishers[publisher]
    changed = False
    summary = {}
    for key, additions in [('authorized_signers', signers or []), ('authorized_releasers', releasers or [])]:
        current = entry.get(key)
        if not isinstance(current, list):
            current = []
        merged = []
        for value in [*current, *additions]:
            if not isinstance(value, str):
                continue
            text = value.strip()
            if not text or text in merged:
                continue
            merged.append(text)
        if merged != current:
            entry[key] = merged
            changed = True
        summary[key] = list(entry.get(key, []))
    if changed:
        write_json(policy_path, payload)
    return {'changed': changed, 'summary': summary}


def current_git_value(root, key):
    result = subprocess.run(['git', 'config', '--get', key], cwd=root, text=True, capture_output=True)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def signer_identities_for_key(entries, public_key):
    normalized = normalize_public_key(public_key)
    if not normalized:
        return []
    matches = []
    for entry in entries:
        if entry.get('normalized_key') == normalized and entry.get('identity') not in matches:
            matches.append(entry['identity'])
    return matches


def default_allowed_signers_path(root=ROOT):
    config = load_json(Path(root) / 'config' / 'signing.json')
    tag_cfg = config.get('git_tag') or {}
    allowed_rel = tag_cfg.get('allowed_signers') or config.get('allowed_signers') or 'config/allowed_signers'
    return (Path(root) / allowed_rel).resolve()


def default_namespace_policy_path(root=ROOT):
    return (Path(root) / 'policy' / 'namespace-policy.json').resolve()
