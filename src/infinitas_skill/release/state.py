"""Release state evaluation and CLI helpers."""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from infinitas_skill.compatibility.policy import load_compatibility_policy
from infinitas_skill.legacy import ROOT, import_legacy_module

compatibility_evidence_lib = import_legacy_module('compatibility_evidence_lib')
exception_policy_lib = import_legacy_module('exception_policy_lib')
policy_pack_lib = import_legacy_module('policy_pack_lib')
policy_trace_lib = import_legacy_module('policy_trace_lib')
review_lib = import_legacy_module('review_lib')
skill_identity_lib = import_legacy_module('skill_identity_lib')
transparency_log_lib = import_legacy_module('transparency_log_lib')

load_compatibility_evidence = compatibility_evidence_lib.load_compatibility_evidence
load_platform_contracts = compatibility_evidence_lib.load_platform_contracts
merge_declared_and_verified_support = compatibility_evidence_lib.merge_declared_and_verified_support

ExceptionPolicyError = exception_policy_lib.ExceptionPolicyError
load_exception_policy = exception_policy_lib.load_exception_policy
match_active_exceptions = exception_policy_lib.match_active_exceptions

PolicyPackError = policy_pack_lib.PolicyPackError
load_policy_domain_resolution = policy_pack_lib.load_policy_domain_resolution

build_policy_trace = policy_trace_lib.build_policy_trace
render_policy_trace = policy_trace_lib.render_policy_trace

ReviewPolicyError = review_lib.ReviewPolicyError
evaluate_review_state = review_lib.evaluate_review_state
review_decision_entries = review_lib.review_decision_entries

NamespacePolicyError = skill_identity_lib.NamespacePolicyError
load_namespace_policy = skill_identity_lib.load_namespace_policy
namespace_policy_report = skill_identity_lib.namespace_policy_report
normalize_skill_identity = skill_identity_lib.normalize_skill_identity

TransparencyLogError = transparency_log_lib.TransparencyLogError
summarize_transparency_log_state = transparency_log_lib.summarize_transparency_log_state

SIGNER_RE = re.compile(r'Good "git" signature for (.+?) with ')
SIGNATURE_MARKERS = ('BEGIN SSH SIGNATURE', 'BEGIN PGP SIGNATURE')
BLOCKING_PLATFORM_STATES = {'unknown', 'blocked', 'broken', 'unsupported'}
BLOCKING_FRESHNESS_STATES = {'stale', 'unknown'}
RELEASE_STATE_MODES = ('preflight', 'local-preflight', 'local-tag', 'stable-release')


class ReleaseError(Exception):
    pass


def _issue(rule_id, message, *, rule=None):
    return {
        'id': rule_id,
        'message': message,
        'rule': rule or message,
    }


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
    try:
        resolution = load_policy_domain_resolution(root, 'signing')
        config = resolution['effective']
        policy_sources = resolution.get('effective_sources', [])
    except PolicyPackError as exc:
        raise ReleaseError('; '.join(exc.errors)) from exc
    tag_cfg = config.get('git_tag') or {}
    allowed_rel = tag_cfg.get('allowed_signers') or config.get('allowed_signers') or 'config/allowed_signers'
    key_env = tag_cfg.get('signing_key_env') or 'INFINITAS_SKILL_GIT_SIGNING_KEY'
    return {
        'config': config,
        'policy_sources': policy_sources,
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


def _release_artifact_paths(root, meta):
    identity = normalize_skill_identity(meta)
    publisher = identity.get('publisher') or '_legacy'
    name = meta.get('name')
    version = meta.get('version')
    return {
        'provenance': root / 'catalog' / 'provenance' / f'{name}-{version}.json',
        'manifest': root / 'catalog' / 'distributions' / publisher / name / version / 'manifest.json',
    }


def _normalize_file_manifest(entries):
    if not isinstance(entries, list):
        return None
    normalized = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        normalized.append(
            {
                'path': entry.get('path'),
                'sha256': entry.get('sha256'),
                'size': entry.get('size'),
                'mode': entry.get('mode'),
            }
        )
    normalized.sort(key=lambda item: item.get('path') or '')
    return normalized


def _normalize_build(build):
    if not isinstance(build, dict):
        return None
    return {
        'archive_format': build.get('archive_format'),
        'gzip_mtime': build.get('gzip_mtime'),
        'tar_mtime': build.get('tar_mtime'),
        'tar_uid': build.get('tar_uid'),
        'tar_gid': build.get('tar_gid'),
        'tar_uname': build.get('tar_uname'),
        'tar_gname': build.get('tar_gname'),
        'builder': build.get('builder'),
    }


def collect_reproducibility_state(root, meta):
    paths = _release_artifact_paths(root, meta)
    summary = {
        'available': False,
        'consistent': True,
        'issues': [],
        'provenance_path': str(paths['provenance'].relative_to(root)) if paths['provenance'].exists() else None,
        'manifest_path': str(paths['manifest'].relative_to(root)) if paths['manifest'].exists() else None,
        'bundle_path': None,
        'bundle_file_count': None,
        'file_manifest_count': 0,
        'archive_format': None,
    }

    provenance_distribution = None
    if paths['provenance'].exists():
        provenance_payload = load_json(paths['provenance'])
        provenance_distribution = provenance_payload.get('distribution') or {}
        bundle = provenance_distribution.get('bundle') or {}
        if isinstance(bundle, dict):
            summary['bundle_path'] = bundle.get('path')
            summary['bundle_file_count'] = bundle.get('file_count')
        file_manifest = provenance_distribution.get('file_manifest')
        if isinstance(file_manifest, list):
            summary['file_manifest_count'] = len(file_manifest)
            summary['available'] = True
        build = provenance_distribution.get('build')
        if isinstance(build, dict):
            summary['archive_format'] = build.get('archive_format')
            summary['available'] = True

    manifest_payload = None
    if paths['manifest'].exists():
        manifest_payload = load_json(paths['manifest'])
        if summary['bundle_path'] is None:
            summary['bundle_path'] = ((manifest_payload.get('bundle') or {}).get('path'))
        if summary['bundle_file_count'] is None:
            summary['bundle_file_count'] = ((manifest_payload.get('bundle') or {}).get('file_count'))
        file_manifest = manifest_payload.get('file_manifest')
        if not summary['available'] and isinstance(file_manifest, list):
            summary['file_manifest_count'] = len(file_manifest)
            summary['available'] = True
        build = manifest_payload.get('build')
        if summary['archive_format'] is None and isinstance(build, dict):
            summary['archive_format'] = build.get('archive_format')
            summary['available'] = True

    if provenance_distribution is not None and manifest_payload is not None:
        normalized_signed_file_manifest = _normalize_file_manifest(provenance_distribution.get('file_manifest'))
        normalized_manifest_file_manifest = _normalize_file_manifest(manifest_payload.get('file_manifest'))
        if normalized_signed_file_manifest is not None or normalized_manifest_file_manifest is not None:
            if normalized_signed_file_manifest != normalized_manifest_file_manifest:
                summary['issues'].append('distribution file manifest does not match signed attestation')

        normalized_signed_build = _normalize_build(provenance_distribution.get('build'))
        normalized_manifest_build = _normalize_build(manifest_payload.get('build'))
        if normalized_signed_build is not None or normalized_manifest_build is not None:
            if normalized_signed_build != normalized_manifest_build:
                summary['issues'].append('distribution build metadata does not match signed attestation')

    summary['consistent'] = not summary['issues']
    return summary


def collect_transparency_log_state(root, meta):
    provenance_path = _release_artifact_paths(root, meta)['provenance']
    if not provenance_path.exists():
        return None
    payload = load_json(provenance_path)
    try:
        summary = summarize_transparency_log_state(provenance_path, payload=payload, root=root)
    except TransparencyLogError as exc:
        return {
            'mode': ((payload.get('transparency_log') or {}).get('mode') if isinstance(payload.get('transparency_log'), dict) else 'unknown'),
            'required': bool(((payload.get('transparency_log') or {}).get('required')) if isinstance(payload.get('transparency_log'), dict) else False),
            'entry_path': ((payload.get('transparency_log') or {}).get('entry_path')) if isinstance(payload.get('transparency_log'), dict) else None,
            'published': False,
            'verified': False,
            'entry_id': None,
            'log_index': None,
            'integrated_time': None,
            'log_endpoint': None,
            'error': str(exc),
        }
    return summary


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
    _reviews, review_entries = review_decision_entries(Path(skill_dir))
    entries = []
    for item in review_entries:
        reviewer = item.get('reviewer')
        decision = item.get('decision')
        if not reviewer or not decision:
            continue
        entries.append({
            'reviewer': reviewer,
            'decision': decision,
            'at': item.get('at'),
            'note': item.get('note'),
            'source': item.get('source'),
            'source_kind': item.get('source_kind'),
            'source_ref': item.get('source_ref'),
            'url': item.get('url'),
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


def collect_platform_compatibility_state(root, meta, identity):
    compatibility_policy = load_compatibility_policy(root)
    platform_contracts = load_platform_contracts(root)
    compatibility_evidence = load_compatibility_evidence(root)
    merged = merge_declared_and_verified_support(
        {
            'name': meta.get('name'),
            'qualified_name': identity.get('qualified_name'),
            'version': meta.get('version'),
            'declared_support': meta.get('agent_compatible') or [],
            'agent_compatible': meta.get('agent_compatible') or [],
        },
        compatibility_evidence,
        platform_contracts=platform_contracts,
        compatibility_policy=compatibility_policy,
    )
    declared_support = merged.get('declared_support') or []
    verified_support = merged.get('verified_support') or {}
    blocking_platforms = []
    for platform in declared_support:
        item = dict(verified_support.get(platform) or {})
        state = item.get('state') or 'unknown'
        freshness_state = item.get('freshness_state') or 'unknown'
        if state in BLOCKING_PLATFORM_STATES or freshness_state in BLOCKING_FRESHNESS_STATES:
            item['platform'] = platform
            blocking_platforms.append(item)

    return {
        'declared_support': declared_support,
        'verified_support': verified_support,
        'blocking_platforms': blocking_platforms,
        'policy': (compatibility_policy.get('verified_support') or {}),
        'evaluation_error': None,
    }


def _format_blocking_platform_support(item):
    parts = []
    state = item.get('state') or 'unknown'
    freshness_state = item.get('freshness_state') or 'unknown'
    parts.append(f'state={state}')
    parts.append(f'freshness={freshness_state}')
    freshness_reason = item.get('freshness_reason')
    if freshness_reason:
        parts.append(f'reason={freshness_reason}')
    checked_at = item.get('checked_at')
    if checked_at:
        parts.append(f'checked_at={checked_at}')
    contract_last_verified = item.get('contract_last_verified')
    if contract_last_verified:
        parts.append(f'contract_last_verified={contract_last_verified}')
    return f"{item.get('platform') or 'unknown'} ({', '.join(parts)})"


def collect_release_state(skill_dir, mode='stable-release', root=None):
    root = Path(root or ROOT).resolve()
    skill_dir = Path(skill_dir).resolve()
    meta, expected_tag = expected_skill_tag(skill_dir)
    identity = normalize_skill_identity(meta)
    reproducibility = collect_reproducibility_state(root, meta)
    transparency_log = collect_transparency_log_state(root, meta)
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
    review_evaluation = None
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
    namespace_policy_sources = []

    issues = []
    warnings = []
    exception_usage = []
    require_clean_worktree = mode != 'local-tag'
    require_upstream_sync = mode in {'preflight', 'stable-release'}
    require_fresh_platform_support = mode in {'preflight', 'stable-release'}
    platform_compatibility = {
        'declared_support': meta.get('agent_compatible') or [],
        'verified_support': {},
        'blocking_platforms': [],
        'policy': {},
        'evaluation_error': None,
    }
    try:
        exception_policy = load_exception_policy(root)
    except ExceptionPolicyError as exc:
        raise ReleaseError('; '.join(exc.errors)) from exc

    try:
        namespace_resolution = load_policy_domain_resolution(root, 'namespace_policy')
        namespace_policy_sources = namespace_resolution.get('effective_sources', [])
        namespace_policy = load_namespace_policy(root)
        namespace_report = namespace_policy_report(skill_dir, root=root, policy=namespace_policy)
    except PolicyPackError as exc:
        issues.extend(_issue('namespace-policy', message) for message in exc.errors)
    except NamespacePolicyError as exc:
        issues.extend(_issue('namespace-policy', message) for message in exc.errors)
    else:
        issues.extend(_issue('namespace-policy', message) for message in namespace_report.get('errors', []))
        warnings.extend(namespace_report.get('warnings', []))

    try:
        review_evaluation = evaluate_review_state(skill_dir, root=root)
    except (PolicyPackError, ReviewPolicyError) as exc:
        warnings.append(f'cannot evaluate review audit state: {"; ".join(exc.errors)}')

    try:
        platform_compatibility = collect_platform_compatibility_state(root, meta, identity)
    except Exception as exc:
        platform_message = f'cannot evaluate platform verified support: {exc}'
        platform_compatibility['evaluation_error'] = platform_message
        if require_fresh_platform_support and platform_compatibility.get('declared_support'):
            issues.append(
                _issue(
                    'platform-verified-support',
                    platform_message,
                    rule='preflight and stable releases require fresh verified support for declared platforms',
                )
            )
        else:
            warnings.append(platform_message)
    else:
        if require_fresh_platform_support and platform_compatibility.get('blocking_platforms'):
            details = ', '.join(
                _format_blocking_platform_support(item) for item in platform_compatibility.get('blocking_platforms', [])
            )
            issues.append(
                _issue(
                    'platform-verified-support',
                    'platform verified support is stale or missing, or the verified state is incompatible, '
                    f'for declared platforms: {details}',
                    rule='preflight and stable releases require fresh verified support for declared platforms',
                )
            )

    if not releaser_identity:
        warnings.append('cannot determine releaser identity; set INFINITAS_SKILL_RELEASER or git config user.name/user.email')
    elif namespace_report.get('authorized_releasers') and releaser_identity not in namespace_report.get('authorized_releasers', []):
        warnings.append(
            f'releaser identity {releaser_identity!r} is not listed in namespace-policy authorized_releasers for {identity.get("qualified_name") or identity.get("name")}'
        )
    if isinstance(transparency_log, dict) and transparency_log.get('error'):
        warnings.append(f'transparency log proof could not be verified: {transparency_log.get("error")}')
    if local_tag.get('signer') and namespace_report.get('authorized_signers') and local_tag['signer'] not in namespace_report.get('authorized_signers', []):
        warnings.append(
            f'tag signer {local_tag["signer"]!r} is not listed in namespace-policy authorized_signers for {identity.get("qualified_name") or identity.get("name")}'
        )

    if dirty:
        if require_clean_worktree:
            issues.append(
                _issue(
                    'dirty-worktree',
                    'worktree is dirty; commit or stash all changes before creating or publishing a stable release',
                    rule='stable releases require a clean worktree',
                )
            )
        else:
            warnings.append('worktree is dirty; local tag release checks allow repo-managed provenance artifacts')
    if require_upstream_sync:
        if not upstream:
            issues.append(
                _issue(
                    'missing-upstream',
                    f'branch {branch or "HEAD"} has no upstream; set one before creating or publishing a stable release',
                    rule='stable releases require upstream synchronization',
                )
            )
        else:
            if ahead:
                issues.append(
                    _issue(
                        'ahead-of-upstream',
                        f'branch is ahead of {upstream} by {ahead} commit(s); push before creating or publishing a stable release',
                        rule='stable releases require upstream synchronization',
                    )
                )
            if behind:
                issues.append(
                    _issue(
                        'behind-of-upstream',
                        f'branch is behind {upstream} by {behind} commit(s); update before creating or publishing a stable release',
                        rule='stable releases require upstream synchronization',
                    )
                )
    elif not upstream:
        warnings.append(
            f'branch {branch or "HEAD"} has no upstream; local tag release checks skip upstream synchronization'
        )
    else:
        if ahead:
            warnings.append(
                f'branch is ahead of {upstream} by {ahead} commit(s); local tag release checks allow this'
            )
        if behind:
            warnings.append(
                f'branch is behind {upstream} by {behind} commit(s); local tag release checks allow this'
            )

    if mode in {'local-tag', 'stable-release'}:
        if not local_tag['exists']:
            issues.append(
                _issue(
                    'missing-local-tag',
                    f'expected release tag is missing: {expected_tag}; create it with scripts/release-skill-tag.sh {meta["name"]} --create',
                    rule='stable releases require a signed verified local tag',
                )
            )
        else:
            if local_tag['ref_type'] != 'tag':
                issues.append(
                    _issue(
                        'lightweight-local-tag',
                        f'{expected_tag} is a lightweight tag; stable releases require a signed annotated tag',
                        rule='stable releases require a signed verified local tag',
                    )
                )
            if not local_tag['signed']:
                issues.append(
                    _issue(
                        'unsigned-local-tag',
                        f'{expected_tag} is not signed; recreate it with scripts/release-skill-tag.sh {meta["name"]} --create --force',
                        rule='stable releases require a signed verified local tag',
                    )
                )
            if not local_tag['verified']:
                detail = local_tag['verification_error'] or 'verification failed'
                issues.append(
                    _issue(
                        'unverified-local-tag',
                        f'{expected_tag} did not verify against repo-managed signers: {detail}',
                        rule='stable releases require a signed verified local tag',
                    )
                )
            if not local_tag['points_to_head']:
                issues.append(
                    _issue(
                        'local-tag-not-head',
                        f'{expected_tag} does not point at HEAD; retag the current release commit before publishing',
                        rule='stable releases require a signed verified local tag',
                    )
                )

    if mode == 'stable-release':
        if not remote_tag['query_ok']:
            issues.append(
                _issue(
                    'remote-tag-query',
                    f'cannot verify pushed tag state on {remote_name}: {remote_tag["query_error"]}',
                    rule='stable releases require remote tag verification in stable-release mode',
                )
            )
        elif not remote_tag['tag_exists']:
            issues.append(
                _issue(
                    'remote-tag-missing',
                    f'{expected_tag} is not pushed to {remote_name}; push it before publishing release output',
                    rule='stable releases require remote tag verification in stable-release mode',
                )
            )
        elif remote_tag['target_commit'] != head_commit:
            issues.append(
                _issue(
                    'remote-tag-mismatch',
                    f'{expected_tag} on {remote_name} points to {remote_tag["target_commit"] or "an unexpected object"}, not HEAD {head_commit}',
                    rule='stable releases require remote tag verification in stable-release mode',
                )
            )

    if mode == 'preflight' and not signer_entries(signing['allowed_signers_path']):
        warnings.append(
            f"{signing['allowed_signers_rel']} has no signer entries yet; signed tag verification will stay blocked until it is populated"
        )

    exception_usage = match_active_exceptions(
        'release',
        meta,
        [item['id'] for item in issues],
        root=root,
        policy=exception_policy,
    )
    waived_rule_ids = {
        matched_rule
        for item in exception_usage
        for matched_rule in item.get('matched_rules', [])
        if isinstance(matched_rule, str) and matched_rule
    }
    remaining_issues = [item for item in issues if item.get('id') not in waived_rule_ids]
    errors = [item['message'] for item in remaining_issues]

    policy_trace = build_policy_trace(
        domain='release_policy',
        decision='allow' if not errors else 'deny',
        summary='release readiness checks passed' if not errors else f'release readiness blocked by {len(errors)} issue(s)',
        effective_sources=list(signing.get('policy_sources', [])) + list(namespace_policy_sources),
        applied_rules=[
            {
                'id': 'dirty-worktree',
                'rule': 'stable releases require a clean worktree',
                'value': {
                    'enforced': require_clean_worktree,
                    'dirty': dirty,
                },
            },
            {
                'id': 'upstream-synchronization',
                'rule': 'stable releases require upstream synchronization',
                'value': {
                    'enforced': require_upstream_sync,
                    'ahead': ahead,
                    'behind': behind,
                },
            },
            {
                'id': 'platform-verified-support',
                'rule': 'preflight and stable releases require fresh verified support for declared platforms',
                'value': {
                    'enforced': require_fresh_platform_support,
                    'declared_support': platform_compatibility.get('declared_support', []),
                    'blocking_platforms': platform_compatibility.get('blocking_platforms', []),
                    'evaluation_error': platform_compatibility.get('evaluation_error'),
                },
            },
            {'id': 'local-tag', 'rule': 'stable releases require a signed verified local tag', 'value': expected_tag},
            {'id': 'remote-tag', 'rule': 'stable releases require remote tag verification in stable-release mode', 'value': mode == 'stable-release'},
            {'id': 'signing-tag-format', 'rule': 'release signing config defines tag_format', 'value': signing['tag_format']},
        ],
        blocking_rules=[{'id': item['id'], 'rule': item['rule'], 'message': item['message']} for item in remaining_issues],
        reasons=warnings + [
            f"mode={mode}",
            f"release_trust_mode={(((signing.get('config') or {}).get('attestation') or {}).get('policy') or {}).get('release_trust_mode', 'ssh')}",
            f"exceptions_applied={len(exception_usage)}",
        ],
        next_actions=[
            'fix the blocking release errors and rerun check-release-state',
            'use --json for machine-readable policy diagnostics',
        ] if errors else ['release policy is satisfied for the current mode'],
        exceptions=exception_usage,
    )

    review_payload = {
        'reviewers': review_entries,
    }
    if review_evaluation:
        review_payload.update(
            {
                'effective_review_state': review_evaluation.get('effective_review_state'),
                'required_approvals': review_evaluation.get('required_approvals'),
                'required_groups': review_evaluation.get('required_groups', []),
                'covered_groups': review_evaluation.get('covered_groups', []),
                'missing_groups': review_evaluation.get('missing_groups', []),
                'approval_count': review_evaluation.get('approval_count'),
                'blocking_rejection_count': review_evaluation.get('blocking_rejection_count'),
                'quorum_met': review_evaluation.get('quorum_met'),
                'review_gate_pass': review_evaluation.get('review_gate_pass'),
                'latest_decisions': review_evaluation.get('latest_decisions', []),
                'ignored_decisions': review_evaluation.get('ignored_decisions', []),
                'configured_groups': review_evaluation.get('configured_groups', {}),
            }
        )

    return {
        'mode': mode,
        'release_ready': not errors,
        'errors': errors,
        'warnings': warnings,
        'exception_usage': exception_usage,
        'policy_trace': policy_trace,
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
        'review': review_payload,
        'release': {
            'releaser_identity': releaser_identity,
            'namespace_policy_path': namespace_report.get('policy_path'),
            'namespace_policy_version': namespace_report.get('policy_version'),
            'transfer_required': namespace_report.get('transfer_required', False),
            'transfer_authorized': namespace_report.get('transfer_authorized', True),
            'transfer_matches': namespace_report.get('transfer_matches', []),
            'competing_claims': namespace_report.get('competing_claims', []),
            'delegated_teams': namespace_report.get('delegated_teams', {}),
            'authorized_signers': namespace_report.get('authorized_signers', []),
            'authorized_releasers': namespace_report.get('authorized_releasers', []),
            'exception_usage': exception_usage,
            'reproducibility': reproducibility,
            'transparency_log': transparency_log,
            'platform_compatibility': platform_compatibility,
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


def build_release_check_state_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description='Check stable release invariants for a skill',
    )
    parser.add_argument('skill', help='Skill name or path')
    parser.add_argument(
        '--mode',
        choices=RELEASE_STATE_MODES,
        default='stable-release',
        help='Which release invariant set to enforce',
    )
    parser.add_argument('--json', action='store_true', help='Print machine-readable state')
    parser.add_argument('--debug-policy', action='store_true', help='Print a human-readable policy trace')
    return parser


def parse_release_check_state_args(argv: list[str] | None = None, *, prog: str | None = None) -> argparse.Namespace:
    return build_release_check_state_parser(prog=prog).parse_args(argv)


def run_release_check_state(
    skill: str,
    *,
    mode: str = 'stable-release',
    as_json: bool = False,
    debug_policy: bool = False,
    root: str | Path | None = None,
) -> int:
    try:
        skill_dir = resolve_skill(Path(root).resolve() if root else ROOT, skill)
        state = collect_release_state(skill_dir, mode=mode, root=root)
    except ReleaseError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print(format_release_state(state))
        if debug_policy:
            print()
            print(render_policy_trace(state.get('policy_trace') or {}))

    return 0 if state['release_ready'] else 1


def release_check_state_main(argv: list[str] | None = None, *, prog: str | None = None) -> int:
    args = parse_release_check_state_args(argv, prog=prog)
    return run_release_check_state(
        args.skill,
        mode=args.mode,
        as_json=args.json,
        debug_policy=args.debug_policy,
    )


__all__ = [
    'ROOT',
    'RELEASE_STATE_MODES',
    'ReleaseError',
    'git',
    'load_json',
    'resolve_skill',
    'load_signing_config',
    'signer_entries',
    'signing_key_path',
    'expected_skill_tag',
    'collect_reproducibility_state',
    'collect_transparency_log_state',
    'collect_platform_compatibility_state',
    'collect_release_state',
    'format_release_state',
    'build_release_check_state_parser',
    'parse_release_check_state_args',
    'run_release_check_state',
    'release_check_state_main',
]
