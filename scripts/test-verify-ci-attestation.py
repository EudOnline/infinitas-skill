#!/usr/bin/env python3
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HELPER_PATH = ROOT / 'scripts' / 'test-attestation-verification.py'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def load_helpers():
    spec = importlib.util.spec_from_file_location('test_attestation_verification_helpers', HELPER_PATH)
    if spec is None or spec.loader is None:
        fail(f'could not load helper module from {HELPER_PATH}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(command, cwd, expect=0, env=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def write_ci_attestation(repo: Path, helpers):
    manifest_path = repo / 'catalog' / 'distributions' / '_legacy' / helpers.FIXTURE_NAME / helpers.FIXTURE_VERSION / 'manifest.json'
    bundle_path = manifest_path.parent / 'skill.tar.gz'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    bundle = manifest.get('bundle') or {}
    head_commit = run(['git', 'rev-parse', 'HEAD'], cwd=repo).stdout.strip()
    env = helpers.make_env(
        {
            'GITHUB_REPOSITORY': 'lvxiaoer/infinitas-skill',
            'GITHUB_WORKFLOW': 'release-attestation',
            'GITHUB_RUN_ID': '123456',
            'GITHUB_RUN_ATTEMPT': '1',
            'GITHUB_SHA': head_commit,
            'GITHUB_REF': f"refs/tags/{helpers.FIXTURE_TAG}",
            'GITHUB_EVENT_NAME': 'workflow_dispatch',
            'GITHUB_SERVER_URL': 'https://github.com',
        }
    )
    result = run(
        [
            sys.executable,
            str(repo / 'scripts' / 'generate-ci-attestation.py'),
            helpers.FIXTURE_NAME,
            '--distribution-manifest-path',
            str(manifest_path.relative_to(repo)),
            '--distribution-bundle-path',
            str(bundle_path.relative_to(repo)),
            '--distribution-bundle-sha256',
            bundle.get('sha256') or '',
            '--distribution-bundle-size',
            str(bundle.get('size') or 0),
            '--distribution-bundle-root-dir',
            bundle.get('root_dir') or '',
            '--distribution-bundle-file-count',
            str(bundle.get('file_count') or 0),
        ],
        cwd=repo,
        env=env,
    )
    ci_path = repo / 'catalog' / 'provenance' / f'{helpers.FIXTURE_NAME}-{helpers.FIXTURE_VERSION}.ci.json'
    ci_path.write_text(result.stdout, encoding='utf-8')
    return ci_path, env


def scenario_verify_ci_attestation_succeeds():
    helpers = load_helpers()
    tmpdir, repo, _origin, _key_path, _identity = helpers.prepare_repo(include_signers=True)
    try:
        run(
            [str(repo / 'scripts' / 'release-skill.sh'), helpers.FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=helpers.make_env(),
        )
        ci_path, env = write_ci_attestation(repo, helpers)
        result = run(
            [sys.executable, str(repo / 'scripts' / 'verify-ci-attestation.py'), str(ci_path), '--json'],
            cwd=repo,
            env=env,
        )
        payload = json.loads(result.stdout)
        if payload.get('verified') is not True:
            fail(f'unexpected verifier payload {payload!r}')
        if payload.get('provider') != 'github-actions':
            fail(f"expected provider 'github-actions', got {payload.get('provider')!r}")
    finally:
        shutil.rmtree(tmpdir)


def scenario_verify_ci_attestation_rejects_wrong_workflow():
    helpers = load_helpers()
    tmpdir, repo, _origin, _key_path, _identity = helpers.prepare_repo(include_signers=True)
    try:
        run(
            [str(repo / 'scripts' / 'release-skill.sh'), helpers.FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=helpers.make_env(),
        )
        ci_path, env = write_ci_attestation(repo, helpers)
        payload = json.loads(ci_path.read_text(encoding='utf-8'))
        payload['ci']['workflow'] = 'unexpected-workflow'
        ci_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result = run(
            [sys.executable, str(repo / 'scripts' / 'verify-ci-attestation.py'), str(ci_path)],
            cwd=repo,
            env=env,
            expect=1,
        )
        if 'FAIL:' not in result.stderr:
            fail(f'expected verifier failure output, got stderr:\n{result.stderr}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_verify_ci_attestation_succeeds()
    scenario_verify_ci_attestation_rejects_wrong_workflow()
    print('OK: CI attestation verification checks passed')


if __name__ == '__main__':
    main()
