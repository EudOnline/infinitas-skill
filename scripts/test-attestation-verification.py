#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_NAME = 'release-fixture'
FIXTURE_VERSION = '1.2.3'
FIXTURE_TAG = f'skill/{FIXTURE_NAME}/v{FIXTURE_VERSION}'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0, env=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def make_env(extra=None):
    env = os.environ.copy()
    env['INFINITAS_SKIP_RELEASE_TESTS'] = '1'
    env['INFINITAS_SKIP_ATTESTATION_TESTS'] = '1'
    env['INFINITAS_SKIP_DISTRIBUTION_TESTS'] = '1'
    env['INFINITAS_SKIP_BOOTSTRAP_TESTS'] = '1'
    env['INFINITAS_SKIP_AI_WRAPPER_TESTS'] = '1'
    env['INFINITAS_SKIP_COMPAT_PIPELINE_TESTS'] = '1'
    if extra:
        env.update(extra)
    return env


def scaffold_fixture(repo: Path):
    fixture_dir = repo / 'skills' / 'active' / FIXTURE_NAME
    shutil.copytree(ROOT / 'templates' / 'basic-skill', fixture_dir)
    meta = json.loads((fixture_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': FIXTURE_NAME,
            'version': FIXTURE_VERSION,
            'status': 'active',
            'summary': 'Fixture skill for stable attestation tests',
            'owner': 'release-test',
            'owners': ['release-test'],
            'author': 'release-test',
            'review_state': 'approved',
        }
    )
    write_json(fixture_dir / '_meta.json', meta)
    (fixture_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {FIXTURE_NAME}\n'
        'description: Fixture skill for release attestation tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated release attestation tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-09\n'
        '- Added stable attestation fixture.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-09T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for attestation tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-09T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def prepare_repo(include_signers=False):
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-attestation-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    scaffold_fixture(repo)
    run(['git', 'init', '--bare', str(origin)], cwd=tmpdir)
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Release Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'release@example.com'], cwd=repo)
    run(['git', 'remote', 'add', 'origin', str(origin)], cwd=repo)
    run(['git', 'add', '.'], cwd=repo)
    run(['git', 'commit', '-m', 'fixture repo'], cwd=repo)
    run(['git', 'push', '-u', 'origin', 'main'], cwd=repo)
    run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
    run(['git', 'add', 'catalog'], cwd=repo)
    run(['git', 'commit', '-m', 'build fixture catalog'], cwd=repo)
    run(['git', 'push'], cwd=repo)

    key_path = None
    identity = 'release-test'
    if include_signers:
        key_path = tmpdir / 'release-test-key'
        run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', identity, '-f', str(key_path)], cwd=repo)
        with (repo / 'config' / 'allowed_signers').open('a', encoding='utf-8') as handle:
            public_key = Path(str(key_path) + '.pub').read_text(encoding='utf-8').strip()
            handle.write(f'{identity} {public_key}\n')
        run(['git', 'config', 'gpg.format', 'ssh'], cwd=repo)
        run(['git', 'config', 'user.signingkey', str(key_path)], cwd=repo)
        run(['git', 'add', 'config/allowed_signers'], cwd=repo)
        run(['git', 'commit', '-m', 'add release signer'], cwd=repo)
        run(['git', 'push'], cwd=repo)
    return tmpdir, repo, origin, key_path, identity


def assert_contains(text, needle, label):
    if needle not in text:
        fail(f'{label} did not include {needle!r}\n{text}')


def scenario_release_notes_require_attestation():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        notes_path = tmpdir / 'release-notes.md'
        result = run(
            [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--notes-out', str(notes_path)],
            cwd=repo,
            expect=1,
            env=make_env(),
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'v9 attestation policy requires --write-provenance', 'notes attestation gate')
    finally:
        shutil.rmtree(tmpdir)


def scenario_verified_attestation_bundle_is_emitted():
    tmpdir, repo, _origin, _key_path, identity = prepare_repo(include_signers=True)
    try:
        result = run(
            [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=make_env(),
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'verified attestation:', 'verified attestation output')
        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        signature_path = provenance_path.with_suffix(provenance_path.suffix + '.ssig')
        distribution_dir = repo / 'catalog' / 'distributions' / '_legacy' / FIXTURE_NAME / FIXTURE_VERSION
        distribution_bundle = distribution_dir / 'skill.tar.gz'
        distribution_manifest = distribution_dir / 'manifest.json'
        distribution_index = repo / 'catalog' / 'distributions.json'
        if not signature_path.exists():
            fail(f'missing attestation signature {signature_path}')
        if not distribution_bundle.exists():
            fail(f'missing distribution bundle {distribution_bundle}')
        if not distribution_manifest.exists():
            fail(f'missing distribution manifest {distribution_manifest}')
        if not distribution_index.exists():
            fail(f'missing distribution index {distribution_index}')
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        if provenance.get('kind') != 'skill-release-attestation':
            fail(f"unexpected attestation kind {provenance.get('kind')!r}")
        if provenance.get('skill', {}).get('author') != identity:
            fail(f"expected skill.author {identity!r}, got {provenance.get('skill', {}).get('author')!r}")
        if provenance.get('attestation', {}).get('signer_identity') != identity:
            fail(
                f"expected signer_identity {identity!r}, got {provenance.get('attestation', {}).get('signer_identity')!r}"
            )
        reviewers = (provenance.get('review') or {}).get('reviewers') or []
        if len(reviewers) != 1 or reviewers[0].get('reviewer') != 'lvxiaoer':
            fail(f'unexpected reviewers payload {reviewers!r}')
        releaser = (provenance.get('release') or {}).get('releaser_identity')
        if releaser != 'Release Fixture':
            fail(f"expected releaser_identity 'Release Fixture', got {releaser!r}")
        if provenance.get('attestation', {}).get('signature_file') != signature_path.name:
            fail(
                f"expected signature_file {signature_path.name!r}, got {provenance.get('attestation', {}).get('signature_file')!r}"
            )
        if provenance.get('git', {}).get('expected_tag') != FIXTURE_TAG:
            fail(f"unexpected expected_tag {provenance.get('git', {}).get('expected_tag')!r}")
        if 'self' not in provenance.get('registry', {}).get('registries_consulted', []):
            fail(f"expected registry context to include self, got {provenance.get('registry', {}).get('registries_consulted')!r}")
        if not provenance.get('dependencies', {}).get('steps'):
            fail('expected dependency steps in attestation payload')
        root_steps = [step for step in provenance['dependencies']['steps'] if step.get('root')]
        if len(root_steps) != 1 or root_steps[0].get('name') != FIXTURE_NAME:
            fail(f"unexpected dependency root steps {root_steps!r}")
        distribution = provenance.get('distribution') or {}
        if (distribution.get('bundle') or {}).get('path') != str(distribution_bundle.relative_to(repo)):
            fail(f"unexpected bundle path {distribution.get('bundle')!r}")
        if distribution.get('manifest_path') != str(distribution_manifest.relative_to(repo)):
            fail(f"unexpected manifest path {distribution.get('manifest_path')!r}")
        run([sys.executable, str(repo / 'scripts' / 'verify-attestation.py'), str(provenance_path)], cwd=repo, env=make_env())
        run([str(repo / 'scripts' / 'verify-provenance-ssh.sh'), str(provenance_path)], cwd=repo, env=make_env())
        run([sys.executable, str(repo / 'scripts' / 'verify-distribution-manifest.py'), str(distribution_manifest)], cwd=repo, env=make_env())
    finally:
        shutil.rmtree(tmpdir)


def scenario_tamper_breaks_attestation():
    tmpdir, repo, _origin, _key_path, _identity = prepare_repo(include_signers=True)
    try:
        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        run(
            [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
            cwd=repo,
            env=make_env(),
        )
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        provenance['skill']['summary'] = 'tampered'
        provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        result = run(
            [sys.executable, str(repo / 'scripts' / 'verify-attestation.py'), str(provenance_path)],
            cwd=repo,
            expect=1,
            env=make_env(),
        )
        combined = result.stdout + result.stderr
        assert_contains(combined, 'FAIL:', 'tampered attestation failure')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_release_notes_require_attestation()
    scenario_verified_attestation_bundle_is_emitted()
    scenario_tamper_breaks_attestation()
    print('OK: attestation verification checks passed')


if __name__ == '__main__':
    main()
