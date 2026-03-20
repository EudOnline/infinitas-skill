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
    env['INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS'] = '1'
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
            'summary': 'Fixture skill for release reproducibility tests',
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
        'description: Fixture skill for release reproducibility tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated reproducibility tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-17\n'
        '- Added release reproducibility fixture.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-17T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for release reproducibility tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-17T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-release-repro-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    (repo / 'config' / 'allowed_signers').write_text('', encoding='utf-8')
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

    key_path = tmpdir / 'release-test-key'
    identity = 'release-test'
    run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', identity, '-f', str(key_path)], cwd=repo)
    with (repo / 'config' / 'allowed_signers').open('a', encoding='utf-8') as handle:
        public_key = Path(str(key_path) + '.pub').read_text(encoding='utf-8').strip()
        handle.write(f'{identity} {public_key}\n')
    run(['git', 'config', 'gpg.format', 'ssh'], cwd=repo)
    run(['git', 'config', 'user.signingkey', str(key_path)], cwd=repo)
    run(['git', 'add', 'config/allowed_signers'], cwd=repo)
    run(['git', 'commit', '-m', 'add release signer'], cwd=repo)
    run(['git', 'push'], cwd=repo)
    return tmpdir, repo


def expect_named_object(payload, key):
    value = payload.get(key)
    if not isinstance(value, dict):
        fail(f'expected {key} to be an object, got {value!r}')
    return value


def expect_file_manifest(payload, label):
    entries = payload.get('file_manifest')
    if not isinstance(entries, list) or not entries:
        fail(f'expected {label}.file_manifest to be a non-empty array, got {entries!r}')
    sample = entries[0]
    if not isinstance(sample, dict):
        fail(f'expected {label}.file_manifest entries to be objects, got {sample!r}')
    for key in ['path', 'sha256', 'size']:
        value = sample.get(key)
        if value in (None, ''):
            fail(f'expected {label}.file_manifest entry to include {key!r}, got {sample!r}')
    if sample.get('path', '').startswith('/'):
        fail(f'expected {label}.file_manifest paths to stay relative, got {sample!r}')
    return entries


def expect_build_metadata(payload, label):
    build = payload.get('build')
    if not isinstance(build, dict):
        fail(f'expected {label}.build to be an object, got {build!r}')
    required = ['archive_format', 'tar_mtime', 'gzip_mtime', 'builder']
    missing = [key for key in required if key not in build]
    if missing:
        fail(f'expected {label}.build to include {missing!r}, got {build!r}')
    if build.get('archive_format') != 'tar.gz':
        fail(f"expected {label}.build.archive_format 'tar.gz', got {build.get('archive_format')!r}")
    if not isinstance(build.get('builder'), dict):
        fail(f'expected {label}.build.builder to be an object, got {build!r}')
    return build


def scenario_release_outputs_include_reproducibility_metadata():
    tmpdir, repo = prepare_repo()
    try:
        run(
            [
                str(repo / 'scripts' / 'release-skill.sh'),
                FIXTURE_NAME,
                '--create-tag',
                '--write-provenance',
                '--local-provenance',
            ],
            cwd=repo,
            env=make_env(),
        )

        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        manifest_path = repo / 'catalog' / 'distributions' / '_legacy' / FIXTURE_NAME / FIXTURE_VERSION / 'manifest.json'
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

        provenance_distribution = expect_named_object(provenance, 'distribution')
        provenance_file_manifest = expect_file_manifest(provenance_distribution, 'provenance.distribution')
        provenance_build = expect_build_metadata(provenance_distribution, 'provenance.distribution')

        manifest_file_manifest = expect_file_manifest(manifest, 'distribution-manifest')
        manifest_build = expect_build_metadata(manifest, 'distribution-manifest')

        bundle = expect_named_object(manifest, 'bundle')
        if len(manifest_file_manifest) != bundle.get('file_count'):
            fail(
                f"expected distribution-manifest.file_manifest length {bundle.get('file_count')!r}, "
                f'got {len(manifest_file_manifest)!r}'
            )
        if len(provenance_file_manifest) != bundle.get('file_count'):
            fail(
                f"expected provenance.distribution.file_manifest length {bundle.get('file_count')!r}, "
                f'got {len(provenance_file_manifest)!r}'
            )
        manifest_paths = {item.get('path') for item in manifest_file_manifest}
        if 'SKILL.md' not in manifest_paths or '_meta.json' not in manifest_paths:
            fail(f'expected file manifest to include SKILL.md and _meta.json, got {sorted(manifest_paths)!r}')
        if provenance_build.get('archive_format') != manifest_build.get('archive_format'):
            fail(f'expected provenance and manifest build metadata to agree, got {provenance_build!r} vs {manifest_build!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_verification_and_release_state_surface_reproducibility_metadata():
    tmpdir, repo = prepare_repo()
    try:
        run(
            [
                str(repo / 'scripts' / 'release-skill.sh'),
                FIXTURE_NAME,
                '--create-tag',
                '--write-provenance',
                '--local-provenance',
            ],
            cwd=repo,
            env=make_env(),
        )

        provenance_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{FIXTURE_VERSION}.json'
        verified = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'verify-attestation.py'),
                str(provenance_path),
                '--json',
            ],
            cwd=repo,
            env=make_env(),
        )
        verified_payload = json.loads(verified.stdout)
        distribution = verified_payload.get('distribution') or {}
        if distribution.get('file_manifest_count', 0) < 1:
            fail(f'expected verify-attestation JSON to expose file_manifest_count, got {verified_payload!r}')
        build = distribution.get('build') or {}
        if build.get('archive_format') != 'tar.gz':
            fail(f'expected verify-attestation JSON to expose build metadata, got {verified_payload!r}')

        release_state = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'check-release-state.py'),
                FIXTURE_NAME,
                '--mode',
                'local-tag',
                '--json',
            ],
            cwd=repo,
            env=make_env(),
        )
        release_payload = json.loads(release_state.stdout)
        reproducibility = ((release_payload.get('release') or {}).get('reproducibility') or {})
        if reproducibility.get('file_manifest_count', 0) < 1:
            fail(f'expected check-release-state JSON to expose reproducibility summary, got {release_payload!r}')
        if reproducibility.get('archive_format') != 'tar.gz':
            fail(f'expected check-release-state JSON to expose archive_format, got {release_payload!r}')

        run(['bash', str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo, env=make_env())
        catalog = json.loads((repo / 'catalog' / 'catalog.json').read_text(encoding='utf-8'))
        catalog_item = next((item for item in catalog.get('skills') or [] if item.get('name') == FIXTURE_NAME), None)
        if not catalog_item:
            fail(f'expected catalog entry for {FIXTURE_NAME}, got {catalog!r}')
        verified_distribution = catalog_item.get('verified_distribution') or {}
        if verified_distribution.get('file_manifest_count', 0) < 1:
            fail(f'expected catalog verified_distribution to expose file_manifest_count, got {catalog_item!r}')
        if verified_distribution.get('build_archive_format') != 'tar.gz':
            fail(f'expected catalog verified_distribution to expose build_archive_format, got {catalog_item!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_distribution_verification_rejects_file_manifest_mismatch():
    tmpdir, repo = prepare_repo()
    try:
        run(
            [
                str(repo / 'scripts' / 'release-skill.sh'),
                FIXTURE_NAME,
                '--create-tag',
                '--write-provenance',
                '--local-provenance',
            ],
            cwd=repo,
            env=make_env(),
        )

        manifest_path = repo / 'catalog' / 'distributions' / '_legacy' / FIXTURE_NAME / FIXTURE_VERSION / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        file_manifest = manifest.get('file_manifest') or []
        if not file_manifest:
            fail(f'expected manifest to include file_manifest before mismatch check, got {manifest!r}')
        file_manifest[0]['sha256'] = '0' * 64
        write_json(manifest_path, manifest)

        mismatch = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'verify-distribution-manifest.py'),
                str(manifest_path),
            ],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        combined = mismatch.stdout + mismatch.stderr
        if 'file manifest' not in combined.lower():
            fail(f'expected file-manifest mismatch failure, got {combined!r}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_release_outputs_include_reproducibility_metadata()
    scenario_verification_and_release_state_surface_reproducibility_metadata()
    scenario_distribution_verification_rejects_file_manifest_mismatch()
    print('OK: release reproducibility checks passed')


if __name__ == '__main__':
    main()
