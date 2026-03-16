#!/usr/bin/env python3
import argparse
import json
import sys
from datetime import datetime, timezone

from attestation_lib import AttestationError, load_attestation_config, resolve_attestation_signer
from provenance_payload_lib import build_common_payload, build_distribution_payload, collect_release_context
from release_lib import ROOT, ReleaseError


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
        '--release-mode',
        choices=['stable-release', 'local-tag'],
        default='stable-release',
        help='Trust mode for the attested source snapshot',
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


def main():
    args = parse_args()
    try:
        context = collect_release_context(args.skill, root=ROOT, releaser=args.releaser, release_mode=args.release_mode)
    except ReleaseError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    try:
        attestation_cfg = load_attestation_config(ROOT)
        signer_identity = resolve_attestation_signer(args.signer, context['state'])
    except AttestationError as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)

    context['generated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    output_name = args.output_name or f"{context['meta'].get('name')}-{context['meta'].get('version')}.json"
    out = build_common_payload(context)
    out['attestation'] = {
        'format': attestation_cfg['format'],
        'namespace': attestation_cfg['namespace'],
        'allowed_signers': attestation_cfg['allowed_signers_rel'],
        'signature_file': f'{output_name}{attestation_cfg["signature_ext"]}',
        'signature_ext': attestation_cfg['signature_ext'],
        'signer_identity': signer_identity,
        'policy_mode': attestation_cfg['policy_mode'],
        'require_verified_attestation_for_release_output': attestation_cfg['require_release_output'],
        'require_verified_attestation_for_distribution': attestation_cfg['require_distribution'],
    }
    distribution = build_distribution_payload(args)
    if distribution:
        out['distribution'] = distribution
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
