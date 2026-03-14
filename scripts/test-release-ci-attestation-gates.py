#!/usr/bin/env python3
import importlib.util
import json
import shutil
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


def set_release_trust_mode(repo: Path, mode: str, helpers):
    signing_path = repo / 'config' / 'signing.json'
    signing = json.loads(signing_path.read_text(encoding='utf-8'))
    signing['attestation']['policy']['release_trust_mode'] = mode
    signing_path.write_text(json.dumps(signing, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    helpers.run(['git', 'add', 'config/signing.json'], cwd=repo)
    helpers.run(['git', 'commit', '-m', f'set release trust mode {mode}'], cwd=repo)
    helpers.run(['git', 'push'], cwd=repo)


def scenario_ci_mode_blocks_release_without_ci_companion():
    helpers = load_helpers()
    tmpdir, repo, _origin, _key_path, _identity = helpers.prepare_repo(include_signers=True)
    try:
        set_release_trust_mode(repo, 'ci', helpers)
        result = helpers.run(
            [str(repo / 'scripts' / 'release-skill.sh'), helpers.FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            expect=1,
            env=helpers.make_env(),
        )
        if 'missing required CI attestation companion' not in (result.stdout + result.stderr):
            fail('expected CI-only mode to block release output without CI companion')
    finally:
        shutil.rmtree(tmpdir)


def scenario_both_mode_blocks_release_without_ci_companion():
    helpers = load_helpers()
    tmpdir, repo, _origin, _key_path, _identity = helpers.prepare_repo(include_signers=True)
    try:
        set_release_trust_mode(repo, 'both', helpers)
        result = helpers.run(
            [str(repo / 'scripts' / 'release-skill.sh'), helpers.FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            expect=1,
            env=helpers.make_env(),
        )
        if 'missing required CI attestation companion' not in (result.stdout + result.stderr):
            fail('expected mixed mode to block release output without CI companion')
    finally:
        shutil.rmtree(tmpdir)


def scenario_manifest_records_required_formats():
    helpers = load_helpers()
    tmpdir, repo, _origin, _key_path, _identity = helpers.prepare_repo(include_signers=True)
    try:
        helpers.run(
            [str(repo / 'scripts' / 'release-skill.sh'), helpers.FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=helpers.make_env(),
        )
        manifest_path = repo / 'catalog' / 'distributions' / '_legacy' / helpers.FIXTURE_NAME / helpers.FIXTURE_VERSION / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        required_formats = (manifest.get('attestation_bundle') or {}).get('required_formats')
        if required_formats != ['ssh']:
            fail(f"expected attestation_bundle.required_formats ['ssh'], got {required_formats!r}")
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_ci_mode_blocks_release_without_ci_companion()
    scenario_both_mode_blocks_release_without_ci_companion()
    scenario_manifest_records_required_formats()
    print('OK: release CI attestation gate checks passed')


if __name__ == '__main__':
    main()
