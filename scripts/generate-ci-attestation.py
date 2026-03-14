#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from attestation_lib import load_attestation_config
from provenance_payload_lib import build_common_payload, build_distribution_payload, collect_release_context
from release_lib import ROOT, ReleaseError


def parse_args():
    parser = argparse.ArgumentParser(description='Generate a CI-native release attestation payload for a skill')
    parser.add_argument('skill', help='Skill name or path')
    parser.add_argument('--output-name', help='Final attestation filename for CI-side sidecar naming')
    parser.add_argument('--releaser', help='Release operator identity override')
    parser.add_argument('--distribution-manifest-path', help='Repository-relative distribution manifest path')
    parser.add_argument('--distribution-bundle-path', help='Repository-relative distribution bundle path')
    parser.add_argument('--distribution-bundle-sha256', help='SHA-256 digest of the distribution bundle')
    parser.add_argument('--distribution-bundle-size', type=int, help='Size in bytes of the distribution bundle')
    parser.add_argument('--distribution-bundle-root-dir', help='Top-level extracted directory name inside the bundle')
    parser.add_argument('--distribution-bundle-file-count', type=int, help='Number of files archived in the bundle')
    return parser.parse_args()


def required_env(name):
    value = os.environ.get(name)
    if not value:
        print(f'FAIL: {name} is required for CI attestation generation', file=sys.stderr)
        raise SystemExit(1)
    return value


def build_ci_metadata():
    repository = required_env('GITHUB_REPOSITORY')
    workflow = required_env('GITHUB_WORKFLOW')
    run_id = required_env('GITHUB_RUN_ID')
    server_url = os.environ.get('GITHUB_SERVER_URL', 'https://github.com').rstrip('/')
    return {
        'provider': 'github-actions',
        'repository': repository,
        'workflow': workflow,
        'run_id': run_id,
        'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT', '1'),
        'sha': required_env('GITHUB_SHA'),
        'ref': required_env('GITHUB_REF'),
        'event_name': os.environ.get('GITHUB_EVENT_NAME'),
        'url': f'{server_url}/{repository}/actions/runs/{run_id}',
    }


def main():
    args = parse_args()
    try:
        context = collect_release_context(
            args.skill,
            root=ROOT,
            releaser=args.releaser,
            ignore_errors=[
                'worktree is dirty',
                'has no upstream',
                'branch is ahead of',
                'branch is behind',
            ],
        )
    except ReleaseError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    attestation_cfg = load_attestation_config(ROOT)
    context['generated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    output_name = args.output_name or f"{context['meta'].get('name')}-{context['meta'].get('version')}.ci.json"
    out = build_common_payload(context)
    out['attestation'] = {
        'format': 'ci',
        'generator': 'github-actions',
        'output_name': output_name,
        'policy_mode': attestation_cfg['policy_mode'],
        'require_verified_attestation_for_release_output': attestation_cfg['require_release_output'],
        'require_verified_attestation_for_distribution': attestation_cfg['require_distribution'],
    }
    out['ci'] = build_ci_metadata()
    distribution = build_distribution_payload(args)
    if distribution:
        out['distribution'] = distribution
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
