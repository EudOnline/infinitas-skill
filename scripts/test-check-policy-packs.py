#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, check=True):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        fail(
            f'command {command!r} exited {result.returncode}, expected 0\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def selector(active_packs=None):
    return {
        '$schema': '../schemas/policy-pack-selection.schema.json',
        'version': 1,
        'compatibility_version': '11-01',
        'description': 'Fixture policy-pack selection',
        'active_packs': active_packs or ['baseline', 'dual-attestation'],
    }


def baseline_pack():
    return {
        '$schema': '../../schemas/policy-pack.schema.json',
        'schema_version': 1,
        'name': 'baseline',
        'description': 'Fixture baseline pack',
        'domains': {
            'promotion_policy': {
                'version': 4,
                'active_requires': {
                    'review_state': ['approved'],
                },
                'reviews': {
                    'groups': {
                        'maintainers': {
                            'members': ['fixture'],
                        }
                    }
                },
            },
            'namespace_policy': {
                'version': 1,
                'publishers': {
                    'fixture': {
                        'owners': ['fixture'],
                    }
                },
            },
            'signing': {
                'namespace': 'infinitas-skill',
                'allowed_signers': 'config/allowed_signers',
                'signature_ext': '.ssig',
                'git_tag': {
                    'format': 'ssh',
                    'allowed_signers': 'config/allowed_signers',
                    'remote': 'origin',
                    'signing_key_env': 'INFINITAS_SKILL_GIT_SIGNING_KEY',
                },
                'attestation': {
                    'format': 'ssh',
                    'namespace': 'infinitas-skill',
                    'allowed_signers': 'config/allowed_signers',
                    'signature_ext': '.ssig',
                    'signing_key_env': 'INFINITAS_SKILL_GIT_SIGNING_KEY',
                    'policy': {
                        'mode': 'enforce',
                        'release_trust_mode': 'ssh',
                        'require_verified_attestation_for_release_output': True,
                        'require_verified_attestation_for_distribution': True,
                    },
                },
            },
            'registry_sources': {
                'default_registry': 'self',
                'registries': [
                    {
                        'name': 'self',
                        'kind': 'git',
                        'url': 'https://example.invalid/self.git',
                        'priority': 100,
                        'enabled': True,
                        'trust': 'private',
                        'allowed_hosts': ['example.invalid'],
                        'allowed_refs': ['refs/heads/main'],
                        'pin': {
                            'mode': 'branch',
                            'value': 'main',
                        },
                        'update_policy': {
                            'mode': 'track',
                        },
                    }
                ],
            },
        },
    }


def dual_attestation_pack():
    return {
        '$schema': '../../schemas/policy-pack.schema.json',
        'schema_version': 1,
        'name': 'dual-attestation',
        'description': 'Fixture second pack',
        'domains': {
            'signing': {
                'attestation': {
                    'policy': {
                        'release_trust_mode': 'both',
                    }
                }
            }
        },
    }


def make_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-check-policy-packs-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', '.worktrees', 'catalog'),
    )
    (repo / 'catalog').mkdir(exist_ok=True)
    write_json(repo / 'policy' / 'policy-packs.json', selector())
    write_json(repo / 'policy' / 'packs' / 'baseline.json', baseline_pack())
    write_json(repo / 'policy' / 'packs' / 'dual-attestation.json', dual_attestation_pack())
    return tmpdir, repo


def checker_path(repo: Path) -> Path:
    return repo / 'scripts' / 'check-policy-packs.py'


def scenario_valid_policy_packs_pass():
    tmpdir, repo = make_repo()
    try:
        result = run([sys.executable, str(checker_path(repo))], cwd=repo, check=False)
        if result.returncode != 0:
            fail(
                'expected valid policy-pack config to pass\n'
                f'stdout:\n{result.stdout}\n'
                f'stderr:\n{result.stderr}'
            )
    finally:
        shutil.rmtree(tmpdir)


def scenario_duplicate_active_pack_names_fail():
    tmpdir, repo = make_repo()
    try:
        write_json(repo / 'policy' / 'policy-packs.json', selector(['baseline', 'baseline']))
        result = run([sys.executable, str(checker_path(repo))], cwd=repo, check=False)
        if result.returncode == 0:
            fail('expected duplicate active pack names to fail validation')
        combined = result.stdout + result.stderr
        if 'duplicate active pack names' not in combined:
            fail(f'expected duplicate active pack validation error, got:\n{combined}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_unknown_pack_file_fails():
    tmpdir, repo = make_repo()
    try:
        write_json(repo / 'policy' / 'policy-packs.json', selector(['baseline', 'missing-pack']))
        result = run([sys.executable, str(checker_path(repo))], cwd=repo, check=False)
        if result.returncode == 0:
            fail('expected unknown pack file to fail validation')
        combined = result.stdout + result.stderr
        if 'missing policy pack file' not in combined:
            fail(f'expected missing policy pack file error, got:\n{combined}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_unknown_policy_domain_fails():
    tmpdir, repo = make_repo()
    try:
        pack = baseline_pack()
        pack['domains']['unsupported_policy'] = {'enabled': True}
        write_json(repo / 'policy' / 'packs' / 'baseline.json', pack)
        result = run([sys.executable, str(checker_path(repo))], cwd=repo, check=False)
        if result.returncode == 0:
            fail('expected invalid policy-pack config to fail validation')
        combined = result.stdout + result.stderr
        if 'unknown policy domain' not in combined:
            fail(f'expected policy-pack validation error to mention unknown policy domain\n{combined}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_non_object_payload_fails():
    tmpdir, repo = make_repo()
    try:
        (repo / 'policy' / 'packs' / 'baseline.json').write_text('[]\n', encoding='utf-8')
        result = run([sys.executable, str(checker_path(repo))], cwd=repo, check=False)
        if result.returncode == 0:
            fail('expected malformed policy-pack payload to fail validation')
        combined = result.stdout + result.stderr
        if 'must contain a JSON object' not in combined:
            fail(f'expected malformed object error, got:\n{combined}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_valid_policy_packs_pass()
    scenario_duplicate_active_pack_names_fail()
    scenario_unknown_pack_file_fails()
    scenario_unknown_policy_domain_fails()
    scenario_non_object_payload_fails()
    print('OK: policy-pack validation checks passed')


if __name__ == '__main__':
    main()
