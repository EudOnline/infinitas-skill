#!/usr/bin/env python3
import importlib.util
import json
import os
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


def scenario_ci_payload_contains_release_and_ci_context():
    helpers = load_helpers()
    tmpdir, repo, _origin, _key_path, _identity = helpers.prepare_repo(include_signers=True)
    try:
        run(
            [str(repo / 'scripts' / 'release-skill.sh'), helpers.FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=helpers.make_env(),
        )
        manifest_path = repo / 'catalog' / 'distributions' / '_legacy' / helpers.FIXTURE_NAME / helpers.FIXTURE_VERSION / 'manifest.json'
        bundle_path = manifest_path.parent / 'skill.tar.gz'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        bundle = manifest.get('bundle') or {}
        env = helpers.make_env(
            {
                'GITHUB_REPOSITORY': 'lvxiaoer/infinitas-skill',
                'GITHUB_WORKFLOW': 'release-attestation',
                'GITHUB_RUN_ID': '123456',
                'GITHUB_RUN_ATTEMPT': '2',
                'GITHUB_SHA': manifest.get('source', {}).get('commit') or 'deadbeef',
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
        payload = json.loads(result.stdout)
        if payload.get('attestation', {}).get('format') != 'ci':
            fail(f"expected attestation.format 'ci', got {payload.get('attestation', {}).get('format')!r}")
        ci = payload.get('ci') or {}
        for key in ['provider', 'repository', 'workflow', 'run_id', 'run_attempt', 'sha', 'ref', 'event_name', 'url']:
            if not ci.get(key):
                fail(f'missing ci.{key}')
        if ci.get('provider') != 'github-actions':
            fail(f"expected ci.provider 'github-actions', got {ci.get('provider')!r}")
        distribution = payload.get('distribution') or {}
        if distribution.get('manifest_path') != str(manifest_path.relative_to(repo)):
            fail(f"unexpected distribution.manifest_path {distribution.get('manifest_path')!r}")
        if (distribution.get('bundle') or {}).get('path') != str(bundle_path.relative_to(repo)):
            fail(f"unexpected distribution bundle path {(distribution.get('bundle') or {}).get('path')!r}")
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_ci_payload_contains_release_and_ci_context()
    print('OK: CI attestation payload checks passed')


if __name__ == '__main__':
    main()
