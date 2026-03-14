#!/usr/bin/env python3
import json
import shutil
import sys
import tempfile
from pathlib import Path

from attestation_lib import AttestationError, load_attestation_config


ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def make_root(config):
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-ci-policy-'))
    config_dir = tmpdir / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / 'allowed_signers').write_text('# test fixture\n', encoding='utf-8')
    write_json(config_dir / 'signing.json', config)
    return tmpdir


def base_config():
    return json.loads((ROOT / 'config' / 'signing.json').read_text(encoding='utf-8'))


def scenario_default_policy_stays_ssh():
    tmpdir = make_root(base_config())
    try:
        result = load_attestation_config(tmpdir)
        if result.get('release_trust_mode') != 'ssh':
            fail(f"expected default release_trust_mode 'ssh', got {result.get('release_trust_mode')!r}")
        if result.get('requires_ssh_attestation') is not True:
            fail('expected requires_ssh_attestation to be true by default')
        if result.get('requires_ci_attestation') is not False:
            fail('expected requires_ci_attestation to be false by default')
    finally:
        shutil.rmtree(tmpdir)


def scenario_ci_only_policy_loads():
    config = base_config()
    config['attestation']['policy']['release_trust_mode'] = 'ci'
    config['attestation']['ci'] = {
        'provider': 'github-actions',
        'repository': 'lvxiaoer/infinitas-skill',
        'workflow': 'release-attestation',
    }
    tmpdir = make_root(config)
    try:
        result = load_attestation_config(tmpdir)
        if result.get('release_trust_mode') != 'ci':
            fail(f"expected release_trust_mode 'ci', got {result.get('release_trust_mode')!r}")
        if result.get('requires_ssh_attestation') is not False:
            fail('expected requires_ssh_attestation false for ci-only mode')
        if result.get('requires_ci_attestation') is not True:
            fail('expected requires_ci_attestation true for ci-only mode')
        ci_policy = result.get('ci') or {}
        if ci_policy.get('provider') != 'github-actions':
            fail(f"expected ci.provider 'github-actions', got {ci_policy.get('provider')!r}")
    finally:
        shutil.rmtree(tmpdir)


def scenario_both_policy_requires_both_paths():
    config = base_config()
    config['attestation']['policy']['release_trust_mode'] = 'both'
    config['attestation']['ci'] = {
        'provider': 'github-actions',
        'repository': 'lvxiaoer/infinitas-skill',
        'workflow': 'release-attestation',
    }
    tmpdir = make_root(config)
    try:
        result = load_attestation_config(tmpdir)
        if result.get('release_trust_mode') != 'both':
            fail(f"expected release_trust_mode 'both', got {result.get('release_trust_mode')!r}")
        if result.get('requires_ssh_attestation') is not True:
            fail('expected requires_ssh_attestation true for both mode')
        if result.get('requires_ci_attestation') is not True:
            fail('expected requires_ci_attestation true for both mode')
    finally:
        shutil.rmtree(tmpdir)


def scenario_invalid_policy_is_rejected():
    config = base_config()
    config['attestation']['policy']['release_trust_mode'] = 'bogus'
    tmpdir = make_root(config)
    try:
        try:
            load_attestation_config(tmpdir)
        except AttestationError:
            return
        fail('expected invalid release_trust_mode to raise AttestationError')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_default_policy_stays_ssh()
    scenario_ci_only_policy_loads()
    scenario_both_policy_requires_both_paths()
    scenario_invalid_policy_is_rejected()
    print('OK: CI attestation policy checks passed')


if __name__ == '__main__':
    main()
