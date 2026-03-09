#!/usr/bin/env python3
import json
import os
import re
import subprocess
from pathlib import Path

from review_lib import load_reviews
from skill_identity_lib import NamespacePolicyError, load_namespace_policy, namespace_policy_report, normalize_skill_identity

ROOT = Path(__file__).resolve().parent.parent
SIGNER_RE = re.compile(r'Good "git" signature for (.+?) with ')
SIGNATURE_MARKERS = ('BEGIN SSH SIGNATURE', 'BEGIN PGP SIGNATURE')


class ReleaseError(Exception):
    pass


def git(root, *args, check=True, extra_config=None):
    command = ['git', '-C', str(root)]
    for key, value in (extra_config or {}).items():
        command.extend(['-c', f'{key}={value}'])
    command.extend(args)
    result = subprocess.run(command, text=True, capture_output=True)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or 'git command failed'
        raise ReleaseError(message)
    return result


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def resolve_skill(root, target):
    candidate = Path(target)
    if candidate.is_dir() and (candidate / '_meta.json').exists():
        return candidate.resolve()
    for stage in ['active', 'incubating', 'archived']:
        skill_dir = root / 'skills' / stage / target
        if skill_dir.is_dir() and (skill_dir / '_meta.json').exists():
            return skill_dir.resolve()
    raise ReleaseError(f'cannot resolve skill: {target}')


def load_signing_config(root):
    config = load_json(root / 'config' / 'signing.json')
    tag_cfg = config.get('git_tag') or {}
    allowed_rel = tag_cfg.get('allowed_signers') or config.get('allowed_signers') or 'config/allowed_signers'
    key_env = tag_cfg.get('signing_key_env') or 'INFINITAS_SKILL_GIT_SIGNING_KEY'
    return {
        'config': config,
        'tag_format': tag_cfg.get('format', 'ssh'),
        'allowed_signers_rel': allowed_rel,
        'allowed_signers_path': (root / allowed_rel).resolve(),
        'default_remote': tag_cfg.get('remote', 'origin'),
        'signing_key_env': key_env,
    }


def signer_entries(path):
    if not Path(path).exists():
        return []
    entries = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        entries.append(stripped)
    return entries


def signing_key_path(root, signing):
    env_value = __import__('os').environ.get(signing['signing_key_env'])
    if env_value:
        return env_value
    result = git(root, 'config', '--get', 'user.signingkey', check=False)
    value = result.stdout.strip()
    return value or None


def expected_skill_tag(skill_dir):
    meta = load_json(skill_dir / '_meta.json')
    return meta, f"skill/{meta['name']}/v{meta['version']}"


def tracked_upstream(root):
    result = git(root, 'rev-parse', '--abbrev-ref', '@{upstream}', check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def split_remote(upstream, default_remote):
    if upstream and '/' in upstream:
        return upstream.split('/', 1)[0]
    return default_remote


def ahead_behind(root, upstream):
    if not upstream:
        return None, None
    result = git(root, 'rev-list', '--left-right', '--count', f'HEAD...{upstream}')
    ahead_text, behind_text = result.stdout.strip().split()
    return int(ahead_text), int(behind_text)


def repo_url(root):
    result = git(root, 'config', '--get', 'remote.origin.url', check=False)
    return result.stdout.strip() or None


def git_config_value(root, key):
    result = git(root, 'config', '--get', key, check=False)
    return result.stdout.strip() or None


def resolve_releaser_identity(root):
    env_value = os.environ.get('INFINITAS_SKILL_RELEASER')
    if env_value and env_value.strip():
        return env_value.strip()
    return git_config_value(root, 'user.name') or git_config_value(root, 'user.email')


def review_audit_entries(skill_dir):
    reviews = load_reviews(Path(skill_dir))
    entries = []
    for item in reviews.get('entries', []):
        reviewer = item.get('reviewer')
        decision = item.get('decision')
        if not reviewer or not decision:
            continue
        entries.append({
            'reviewer': reviewer,
            'decision': decision,
            'at': item.get('at'),
            'note': item.get('note'),
        })
    return entries


def _tag_signature_markers(root, tag_name):
    result = git(root, 'cat-file', '-p', tag_name, check=False)
    if result.returncode != 0:
        return ''
    return result.stdout


def local_tag_state(root, tag_name, signing):
    state = {
        'exists': False,
        'ref_type': None,
        'target_commit': None,
        'points_to_head': False,
        'signed': False,
        'verified': False,
        'signer': None,
        'verification_output': None,
        'verification_error': None,
    }
    if git(root, 'rev-parse', '-q', '--verify', f'refs/tags/{tag_name}', check=False).returncode != 0:
        return state
    state['exists'] = True
    ref_type = git(root, 'cat-file', '-t', f'refs/tags/{tag_name}', check=False).stdout.strip() or None
    state['ref_type'] = ref_type
    target = git(root, 'rev-parse', f'{tag_name}^{{}}', check=False).stdout.strip() or None
    state['target_commit'] = target
    if ref_type == 'tag':
        payload = _tag_signature_markers(root, tag_name)
        state['signed'] = any(marker in payload for marker in SIGNATURE_MARKERS)
        entries = signer_entries(signing['allowed_signers_path'])
        if signing['tag_format'] == 'ssh' and not entries:
            state['verification_error'] = (
                f"{signing['allowed_signers_rel']} has no signer entries; "
                'add trusted release signers before verifying stable release tags'
            )
            return state
        verify = git(
            root,
            'tag',
            '-v',
            tag_name,
            check=False,
            extra_config={
                'gpg.format': signing['tag_format'],
                'gpg.ssh.allowedSignersFile': str(signing['allowed_signers_path']),
            },
        )
        combined = '\n'.join(part for part in [verify.stdout.strip(), verify.stderr.strip()] if part).strip() or None
        if verify.returncode == 0:
            state['verified'] = True
            state['verification_output'] = combined
            signer_match = SIGNER_RE.search(combined or '')
            if signer_match:
                state['signer'] = signer_match.group(1).strip()
        else:
            state['verification_error'] = combined or 'tag verification failed'
    return state


def remote_tag_state(root, remote_name, tag_name):
    state = {
        'name': remote_name,
        'query_ok': True,
        'query_error': None,
        'tag_exists': False,
        'tag_object': None,
        'target_commit': None,
    }
    if not remote_name:
        state['query_ok'] = False
        state['query_error'] = 'no remote configured'
        return state
    result = git(
        root,
        'ls-remote',
        '--tags',
        remote_name,
        f'refs/tags/{tag_name}',
        f'refs/tags/{tag_name}^{{}}',
        check=False,
    )
    if result.returncode != 0:
        state['query_ok'] = False
        state['query_error'] = result.stderr.strip() or result.stdout.strip() or f'cannot query remote {remote_name}'
        return state
    for line in result.stdout.splitlines():
        oid, ref = line.split('\t', 1)
        if ref == f'refs/tags/{tag_name}':
            state['tag_exists'] = True
            state['tag_object'] = oid
        elif ref == f'refs/tags/{tag_name}^{{}}':
            state['tag_exists'] = True
            state['target_commit'] = oid
    return state


def collect_release_state(skill_dir, mode='stable-release', root=None):
    root = Path(root or ROOT).resolve()
    skill_dir = Path(skill_dir).resolve()
    meta, expected_tag = expected_skill_tag(skill_dir)
    identity = normalize_skill_identity(meta)
    signing = load_signing_config(root)
    head_commit = git(root, 'rev-parse', 'HEAD').stdout.strip()
    branch = git(root, 'branch', '--show-current', check=False).stdout.strip() or None
    upstream = tracked_upstream(root)
    remote_name = split_remote(upstream, signing['default_remote'])
    ahead, behind = ahead_behind(root, upstream)
    dirty = bool(git(root, 'status', '--porcelain').stdout.strip())
    local_tag = local_tag_state(root, expected_tag, signing)
    local_tag['points_to_head'] = bool(local_tag['target_commit'] and local_tag['target_commit'] == head_commit)
    remote_tag = remote_tag_state(root, remote_name, expected_tag)
    review_entries = review_audit_entries(skill_dir)
    releaser_identity = resolve_releaser_identity(root)
    namespace_report = {
        'policy_path': None,
        'policy_version': None,
        'authorized_signers': [],
        'authorized_releasers': [],
        'transfer_required': False,
        'transfer_authorized': True,
        'transfer_matches': [],
        'competing_claims': [],
        'warnings': [],
        'errors': [],
    }

    errors = []
    warnings = []

    try:
        namespace_policy = load_namespace_policy(root)
        namespace_report = namespace_policy_report(skill_dir, root=root, policy=namespace_policy)
    except NamespacePolicyError as exc:
        errors.extend(exc.errors)
    else:
        errors.extend(namespace_report.get('errors', []))
        warnings.extend(namespace_report.get('warnings', []))

    if not releaser_identity:
        warnings.append('cannot determine releaser identity; set INFINITAS_SKILL_RELEASER or git config user.name/user.email')
    elif namespace_report.get('authorized_releasers') and releaser_identity not in namespace_report.get('authorized_releasers', []):
        warnings.append(
            f'releaser identity {releaser_identity!r} is not listed in namespace-policy authorized_releasers for {identity.get("qualified_name") or identity.get("name")}'
        )
    if local_tag.get('signer') and namespace_report.get('authorized_signers') and local_tag['signer'] not in namespace_report.get('authorized_signers', []):
        warnings.append(
            f'tag signer {local_tag["signer"]!r} is not listed in namespace-policy authorized_signers for {identity.get("qualified_name") or identity.get("name")}'
        )

    if dirty:
        errors.append('worktree is dirty; commit or stash all changes before creating or publishing a stable release')
    if not upstream:
        errors.append(
            f'branch {branch or "HEAD"} has no upstream; set one before creating or publishing a stable release'
        )
    else:
        if ahead:
            errors.append(f'branch is ahead of {upstream} by {ahead} commit(s); push before creating or publishing a stable release')
        if behind:
            errors.append(f'branch is behind {upstream} by {behind} commit(s); update before creating or publishing a stable release')

    if mode in {'local-tag', 'stable-release'}:
        if not local_tag['exists']:
            errors.append(
                f'expected release tag is missing: {expected_tag}; create it with scripts/release-skill-tag.sh {meta["name"]} --create'
            )
        else:
            if local_tag['ref_type'] != 'tag':
                errors.append(
                    f'{expected_tag} is a lightweight tag; stable releases require a signed annotated tag'
                )
            if not local_tag['signed']:
                errors.append(
                    f'{expected_tag} is not signed; recreate it with scripts/release-skill-tag.sh {meta["name"]} --create --force'
                )
            if not local_tag['verified']:
                detail = local_tag['verification_error'] or 'verification failed'
                errors.append(f'{expected_tag} did not verify against repo-managed signers: {detail}')
            if not local_tag['points_to_head']:
                errors.append(f'{expected_tag} does not point at HEAD; retag the current release commit before publishing')

    if mode == 'stable-release':
        if not remote_tag['query_ok']:
            errors.append(f'cannot verify pushed tag state on {remote_name}: {remote_tag["query_error"]}')
        elif not remote_tag['tag_exists']:
            errors.append(
                f'{expected_tag} is not pushed to {remote_name}; push it before publishing release output'
            )
        elif remote_tag['target_commit'] != head_commit:
            errors.append(
                f'{expected_tag} on {remote_name} points to {remote_tag["target_commit"] or "an unexpected object"}, not HEAD {head_commit}'
            )

    if mode == 'preflight' and not signer_entries(signing['allowed_signers_path']):
        warnings.append(
            f"{signing['allowed_signers_rel']} has no signer entries yet; signed tag verification will stay blocked until it is populated"
        )

    return {
        'mode': mode,
        'release_ready': not errors,
        'errors': errors,
        'warnings': warnings,
        'skill': {
            'name': meta.get('name'),
            'publisher': identity.get('publisher'),
            'qualified_name': identity.get('qualified_name'),
            'identity_mode': identity.get('identity_mode'),
            'version': meta.get('version'),
            'status': meta.get('status'),
            'path': str(skill_dir.relative_to(root)),
            'author': identity.get('author'),
            'owners': identity.get('owners', []),
            'maintainers': identity.get('maintainers', []),
        },
        'review': {
            'reviewers': review_entries,
        },
        'release': {
            'releaser_identity': releaser_identity,
            'namespace_policy_path': namespace_report.get('policy_path'),
            'namespace_policy_version': namespace_report.get('policy_version'),
            'transfer_required': namespace_report.get('transfer_required', False),
            'transfer_authorized': namespace_report.get('transfer_authorized', True),
            'transfer_matches': namespace_report.get('transfer_matches', []),
            'competing_claims': namespace_report.get('competing_claims', []),
            'authorized_signers': namespace_report.get('authorized_signers', []),
            'authorized_releasers': namespace_report.get('authorized_releasers', []),
        },
        'signing': {
            'tag_format': signing['tag_format'],
            'allowed_signers': signing['allowed_signers_rel'],
            'signer_count': len(signer_entries(signing['allowed_signers_path'])),
            'signing_key_env': signing['signing_key_env'],
            'signing_key': signing_key_path(root, signing),
        },
        'git': {
            'repo_url': repo_url(root),
            'branch': branch,
            'head_commit': head_commit,
            'upstream': upstream,
            'ahead': ahead,
            'behind': behind,
            'dirty': dirty,
            'expected_tag': expected_tag,
            'local_tag': local_tag,
            'remote_tag': remote_tag,
        },
    }


def format_release_state(state):
    lines = [
        f"skill: {state['skill']['name']}",
        f"version: {state['skill']['version']}",
        f"qualified_name: {state['skill'].get('qualified_name') or '-'}",
        f"mode: {state['mode']}",
        f"branch: {state['git']['branch'] or '-'}",
        f"upstream: {state['git']['upstream'] or '-'}",
        f"head: {state['git']['head_commit']}",
        f"expected_tag: {state['git']['expected_tag']}",
        f"releaser: {(state.get('release') or {}).get('releaser_identity') or '-'}",
        f"release_ready: {'yes' if state['release_ready'] else 'no'}",
    ]
    if state['warnings']:
        lines.append('warnings:')
        lines.extend(f'- {item}' for item in state['warnings'])
    if state['errors']:
        lines.append('errors:')
        lines.extend(f'- {item}' for item in state['errors'])
    return '\n'.join(lines)
