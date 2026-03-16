#!/usr/bin/env python3
import json
from pathlib import Path

from dependency_lib import plan_from_skill_dir
from registry_source_lib import find_registry, load_registry_config, registry_identity
from release_lib import ROOT, ReleaseError, collect_release_state, resolve_skill


def unique(values):
    result = []
    seen = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def collect_release_context(skill, root=None, releaser=None, ignore_errors=None, release_mode='stable-release'):
    root = Path(root or ROOT).resolve()
    skill_dir = resolve_skill(root, skill)
    state = collect_release_state(skill_dir, mode=release_mode, root=root)
    ignore_errors = ignore_errors or []
    filtered_errors = [
        error for error in state['errors'] if not any(ignored in error for ignored in ignore_errors)
    ]
    if filtered_errors:
        raise ReleaseError('; '.join(filtered_errors))

    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    registry_cfg = load_registry_config(root)
    default_registry = registry_cfg.get('default_registry')
    default_registry_entry = find_registry(registry_cfg, default_registry) if default_registry else None
    source_info = registry_identity(root, default_registry_entry) if default_registry_entry else {'registry_name': default_registry}
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
            resolved_registries.append(registry_identity(root, reg))
        else:
            resolved_registries.append({'registry_name': name, 'missing': True})

    remote_tag = state['git']['remote_tag']
    local_tag = state['git']['local_tag']
    tag_name = state['git']['expected_tag']
    commit = remote_tag.get('target_commit') or local_tag.get('target_commit') or state['git']['head_commit']
    review = state.get('review') or {}
    release = state.get('release') or {}
    releaser_identity = releaser or release.get('releaser_identity')
    if not releaser_identity:
        raise ReleaseError(
            'cannot determine releaser identity; pass --releaser or set INFINITAS_SKILL_RELEASER / git user.name'
        )

    return {
        'root': root,
        'skill_dir': skill_dir,
        'release_mode': release_mode,
        'state': state,
        'meta': meta,
        'default_registry': default_registry,
        'dependency_plan': dependency_plan,
        'consulted_registries': consulted_registries,
        'resolved_registries': resolved_registries,
        'review': review,
        'release': release,
        'releaser_identity': releaser_identity,
        'tag_name': tag_name,
        'commit': commit,
        'remote_tag': remote_tag,
        'local_tag': local_tag,
    }


def build_common_payload(context):
    meta = context['meta']
    state = context['state']
    release_mode = context.get('release_mode') or 'stable-release'
    pushed = release_mode == 'stable-release'
    review_payload = dict(context.get('review') or {})
    review_payload.setdefault('reviewers', [])
    release_payload = dict(context.get('release') or {})
    release_payload['releaser_identity'] = context['releaser_identity']
    release_payload['release_mode'] = release_mode
    return {
        '$schema': 'schemas/provenance.schema.json',
        'schema_version': 1,
        'kind': 'skill-release-attestation',
        'generated_at': context['generated_at'],
        'skill': {
            'name': meta.get('name'),
            'publisher': state.get('skill', {}).get('publisher'),
            'qualified_name': state.get('skill', {}).get('qualified_name'),
            'identity_mode': state.get('skill', {}).get('identity_mode'),
            'version': meta.get('version'),
            'status': meta.get('status'),
            'summary': meta.get('summary'),
            'path': str(context['skill_dir'].relative_to(context['root'])),
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
            'commit': context['commit'],
            'head_commit': state['git'].get('head_commit'),
            'expected_tag': context['tag_name'],
            'release_ref': f"refs/tags/{context['tag_name']}",
            'remote': context['remote_tag'].get('name') if pushed else None,
            'remote_tag_object': context['remote_tag'].get('tag_object') if pushed else None,
            'remote_tag_commit': context['remote_tag'].get('target_commit') if pushed else None,
            'signed_tag_verified': True,
            'tag_signer': context['local_tag'].get('signer'),
        },
        'source_snapshot': {
            'kind': 'git-tag',
            'tag': context['tag_name'],
            'ref': f"refs/tags/{context['tag_name']}",
            'commit': context['commit'],
            'remote': context['remote_tag'].get('name') if pushed else None,
            'upstream': state['git'].get('upstream'),
            'immutable': True,
            'pushed': pushed,
        },
        'registry': {
            'default_registry': context['default_registry'],
            'registries_consulted': context['consulted_registries'],
            'resolved': context['resolved_registries'],
        },
        'dependencies': context['dependency_plan'],
        'review': review_payload,
        'release': release_payload,
    }


def build_distribution_payload(args):
    if not args.distribution_bundle_path:
        return None
    return {
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
