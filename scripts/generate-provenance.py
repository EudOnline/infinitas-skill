#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone

from attestation_lib import AttestationError, load_attestation_config, resolve_attestation_signer
from dependency_lib import plan_from_skill_dir
from registry_source_lib import find_registry, load_registry_config, registry_identity
from release_lib import ROOT, ReleaseError, collect_release_state, resolve_skill


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a stable release attestation payload for a skill')
    parser.add_argument('skill', help='Skill name or path')
    parser.add_argument(
        '--output-name',
        help='Final attestation filename; used to record the detached signature sidecar name',
    )
    parser.add_argument(
        '--signer',
        help='Attestation signer identity; defaults to the verified release tag signer',
    )
    parser.add_argument(
        '--releaser',
        help='Release operator identity; defaults to INFINITAS_SKILL_RELEASER or git user.name/user.email',
    )
    parser.add_argument(
        '--distribution-manifest-path',
        help='Repository-relative distribution manifest path to bind into the signed attestation payload',
    )
    parser.add_argument(
        '--distribution-bundle-path',
        help='Repository-relative distribution bundle path to bind into the signed attestation payload',
    )
    parser.add_argument(
        '--distribution-bundle-sha256',
        help='SHA-256 digest of the distribution bundle',
    )
    parser.add_argument(
        '--distribution-bundle-size',
        type=int,
        help='Size in bytes of the distribution bundle',
    )
    parser.add_argument(
        '--distribution-bundle-root-dir',
        help='Top-level extracted directory name inside the distribution bundle',
    )
    parser.add_argument(
        '--distribution-bundle-file-count',
        type=int,
        help='Number of files archived in the distribution bundle',
    )
    return parser.parse_args()


def unique(values):
    result = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def main():
    args = parse_args()
    try:
        skill_dir = resolve_skill(ROOT, args.skill)
        state = collect_release_state(skill_dir, mode='stable-release')
    except ReleaseError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    if not state['release_ready']:
        for error in state['errors']:
            print(f'FAIL: {error}', file=sys.stderr)
        raise SystemExit(1)

    try:
        attestation_cfg = load_attestation_config(ROOT)
        signer_identity = resolve_attestation_signer(args.signer, state)
    except AttestationError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    registry_cfg = load_registry_config(ROOT)
    default_registry = registry_cfg.get('default_registry')
    default_registry_entry = find_registry(registry_cfg, default_registry) if default_registry else None
    source_info = registry_identity(ROOT, default_registry_entry) if default_registry_entry else {'registry_name': default_registry}
    dependency_plan = plan_from_skill_dir(
        skill_dir,
        source_registry=default_registry,
        source_info=source_info,
        mode='install',
    )

    consulted_registries = unique(
        [default_registry]
        + list(dependency_plan.get('registries_consulted', []))
        + [step.get('registry') for step in dependency_plan.get('steps', [])]
    )
    resolved_registries = []
    for name in consulted_registries:
        reg = find_registry(registry_cfg, name)
        if reg:
            resolved_registries.append(registry_identity(ROOT, reg))
        else:
            resolved_registries.append({'registry_name': name, 'missing': True})

    remote_tag = state['git']['remote_tag']
    local_tag = state['git']['local_tag']
    tag_name = state['git']['expected_tag']
    commit = remote_tag.get('target_commit') or local_tag.get('target_commit') or state['git']['head_commit']
    output_name = args.output_name or f"{meta.get('name')}-{meta.get('version')}.json"
    review = state.get('review') or {}
    release = state.get('release') or {}
    releaser_identity = args.releaser or release.get('releaser_identity')
    if not releaser_identity:
        print('FAIL: cannot determine releaser identity; pass --releaser or set INFINITAS_SKILL_RELEASER / git user.name', file=sys.stderr)
        raise SystemExit(1)

    out = {
        '$schema': 'schemas/provenance.schema.json',
        'schema_version': 1,
        'kind': 'skill-release-attestation',
        'generated_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'skill': {
            'name': meta.get('name'),
            'publisher': state.get('skill', {}).get('publisher'),
            'qualified_name': state.get('skill', {}).get('qualified_name'),
            'identity_mode': state.get('skill', {}).get('identity_mode'),
            'version': meta.get('version'),
            'status': meta.get('status'),
            'summary': meta.get('summary'),
            'path': str(skill_dir.relative_to(ROOT)),
            'author': state.get('skill', {}).get('author'),
            'owners': state.get('skill', {}).get('owners', []),
            'maintainers': state.get('skill', {}).get('maintainers', []),
            'derived_from': meta.get('derived_from'),
            'snapshot_of': meta.get('snapshot_of'),
            'depends_on': meta.get('depends_on', []),
            'conflicts_with': meta.get('conflicts_with', []),
        },
        'git': {
            'repo_url': state['git'].get('repo_url'),
            'branch': state['git'].get('branch'),
            'upstream': state['git'].get('upstream'),
            'commit': commit,
            'head_commit': state['git'].get('head_commit'),
            'expected_tag': tag_name,
            'release_ref': f'refs/tags/{tag_name}',
            'remote': remote_tag.get('name'),
            'remote_tag_object': remote_tag.get('tag_object'),
            'remote_tag_commit': remote_tag.get('target_commit'),
            'signed_tag_verified': True,
            'tag_signer': local_tag.get('signer'),
        },
        'source_snapshot': {
            'kind': 'git-tag',
            'tag': tag_name,
            'ref': f'refs/tags/{tag_name}',
            'commit': commit,
            'remote': remote_tag.get('name'),
            'upstream': state['git'].get('upstream'),
            'immutable': True,
            'pushed': True,
        },
        'registry': {
            'default_registry': default_registry,
            'registries_consulted': consulted_registries,
            'resolved': resolved_registries,
        },
        'dependencies': dependency_plan,
        'review': {
            'reviewers': review.get('reviewers', []),
        },
        'release': {
            'releaser_identity': releaser_identity,
            'namespace_policy_path': release.get('namespace_policy_path'),
            'namespace_policy_version': release.get('namespace_policy_version'),
            'transfer_required': release.get('transfer_required', False),
            'transfer_authorized': release.get('transfer_authorized', True),
            'transfer_matches': release.get('transfer_matches', []),
            'competing_claims': release.get('competing_claims', []),
            'authorized_signers': release.get('authorized_signers', []),
            'authorized_releasers': release.get('authorized_releasers', []),
        },
        'attestation': {
            'format': attestation_cfg['format'],
            'namespace': attestation_cfg['namespace'],
            'allowed_signers': attestation_cfg['allowed_signers_rel'],
            'signature_file': f'{output_name}{attestation_cfg["signature_ext"]}',
            'signature_ext': attestation_cfg['signature_ext'],
            'signer_identity': signer_identity,
            'policy_mode': attestation_cfg['policy_mode'],
            'require_verified_attestation_for_release_output': attestation_cfg['require_release_output'],
            'require_verified_attestation_for_distribution': attestation_cfg['require_distribution'],
        },
    }
    if args.distribution_bundle_path:
        out['distribution'] = {
            'manifest_path': args.distribution_manifest_path,
            'bundle': {
                'path': args.distribution_bundle_path,
                'format': 'tar.gz',
                'sha256': args.distribution_bundle_sha256,
                'size': args.distribution_bundle_size,
                'root_dir': args.distribution_bundle_root_dir,
                'file_count': args.distribution_bundle_file_count,
            },
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
