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
VERSION = '1.2.3'


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
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    shutil.copytree(ROOT / 'templates' / 'basic-skill', fixture_dir)
    meta = json.loads((fixture_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': FIXTURE_NAME,
            'version': VERSION,
            'status': 'active',
            'summary': f'Fixture skill version {VERSION} for installed integrity tests',
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
        'description: Fixture skill for installed integrity tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        f'Current fixture version: {VERSION}.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'VERSION.txt').write_text(VERSION + '\n', encoding='utf-8')
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {VERSION} - 2026-03-18\n'
        '- Prepared fixture release for installed integrity tests.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-18T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for installed integrity tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-18T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-installed-integrity-'))
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


def release_fixture(repo: Path):
    run(
        [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
        cwd=repo,
        env=make_env(),
    )


def install_fixture(repo: Path, target_dir: Path):
    run(
        [str(repo / 'scripts' / 'install-skill.sh'), FIXTURE_NAME, str(target_dir), '--version', VERSION],
        cwd=repo,
        env=make_env(),
    )


def read_install_manifest(target_dir: Path):
    manifest_path = target_dir / '.infinitas-skill-install-manifest.json'
    if not manifest_path.exists():
        fail(f'missing install manifest {manifest_path}')
    return json.loads(manifest_path.read_text(encoding='utf-8'))


def verify_installed_skill(repo: Path, target_dir: Path, *, expect=0):
    result = run(
        [sys.executable, str(repo / 'scripts' / 'verify-installed-skill.py'), FIXTURE_NAME, str(target_dir), '--json'],
        cwd=repo,
        env=make_env(),
        expect=expect,
    )
    if not result.stdout.strip():
        fail('verify-installed-skill.py did not print JSON output')
    return json.loads(result.stdout)


def scenario_verify_clean_and_drifted_install():
    tmpdir, repo = prepare_repo()
    try:
        release_fixture(repo)
        target_dir = tmpdir / 'installed'
        target_dir.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_dir)

        manifest = read_install_manifest(target_dir)
        current = ((manifest.get('skills') or {}).get(FIXTURE_NAME) or {})
        integrity = current.get('integrity')
        if not isinstance(integrity, dict):
            fail(f'expected install manifest integrity block, got {integrity!r}')
        if integrity.get('state') != 'verified':
            fail(f"expected install integrity state 'verified', got {integrity.get('state')!r}")
        if current.get('integrity_capability') != 'supported':
            fail(f"expected install integrity_capability 'supported', got {current.get('integrity_capability')!r}")
        if current.get('integrity_reason') is not None:
            fail(f"expected install integrity_reason to stay null, got {current.get('integrity_reason')!r}")
        integrity_events = current.get('integrity_events')
        if not isinstance(integrity_events, list) or not integrity_events:
            fail(f'expected install manifest integrity_events to include baseline history, got {current!r}')
        first_event = integrity_events[0]
        if not isinstance(first_event, dict) or first_event.get('event') != 'verified':
            fail(f"expected first integrity event to be 'verified', got {current!r}")
        if not integrity.get('last_verified_at'):
            fail('expected install integrity last_verified_at to be populated')
        if integrity.get('checked_file_count') != integrity.get('release_file_manifest_count'):
            fail(
                'expected install integrity checked_file_count to equal release_file_manifest_count, '
                f"got {integrity.get('checked_file_count')!r} vs {integrity.get('release_file_manifest_count')!r}"
            )
        if integrity.get('modified_count') != 0 or integrity.get('missing_count') != 0 or integrity.get('unexpected_count') != 0:
            fail(f'expected zero install integrity drift counts, got {integrity!r}')

        listed = run([str(repo / 'scripts' / 'list-installed.sh'), str(target_dir)], cwd=repo).stdout
        if 'integrity=verified' not in listed:
            fail(f'expected list-installed output to surface integrity=verified\n{listed}')

        payload = verify_installed_skill(repo, target_dir)
        if payload.get('state') != 'verified':
            fail(f"expected verified state, got {payload.get('state')!r}")
        if payload.get('qualified_name') != FIXTURE_NAME:
            fail(f"expected qualified_name {FIXTURE_NAME!r}, got {payload.get('qualified_name')!r}")
        if payload.get('installed_version') != VERSION:
            fail(f"expected installed_version {VERSION!r}, got {payload.get('installed_version')!r}")
        manifest_path = payload.get('source_distribution_manifest') or ''
        if f'/{VERSION}/manifest.json' not in manifest_path:
            fail(f'unexpected source_distribution_manifest {manifest_path!r}')
        attestation_path = payload.get('source_attestation_path') or ''
        if f'{FIXTURE_NAME}-{VERSION}.json' not in attestation_path:
            fail(f'unexpected source_attestation_path {attestation_path!r}')
        if payload.get('release_file_manifest_count', 0) < 1:
            fail(f"expected release_file_manifest_count > 0, got {payload.get('release_file_manifest_count')!r}")
        if payload.get('checked_file_count') != payload.get('release_file_manifest_count'):
            fail(
                'expected checked_file_count to equal release_file_manifest_count for a clean install, '
                f"got {payload.get('checked_file_count')!r} vs {payload.get('release_file_manifest_count')!r}"
            )
        if payload.get('modified_files') != []:
            fail(f"expected modified_files [], got {payload.get('modified_files')!r}")
        if payload.get('missing_files') != []:
            fail(f"expected missing_files [], got {payload.get('missing_files')!r}")
        if payload.get('unexpected_files') != []:
            fail(f"expected unexpected_files [], got {payload.get('unexpected_files')!r}")

        installed_dir = target_dir / FIXTURE_NAME
        with (installed_dir / 'SKILL.md').open('a', encoding='utf-8') as handle:
            handle.write('\nLocal drift.\n')
        (installed_dir / 'tests' / 'smoke.md').unlink()
        (installed_dir / 'local-notes.txt').write_text('temporary local note\n', encoding='utf-8')

        drift_payload = verify_installed_skill(repo, target_dir, expect=1)
        if drift_payload.get('state') != 'drifted':
            fail(f"expected drifted state, got {drift_payload.get('state')!r}")
        if drift_payload.get('modified_files') != ['SKILL.md']:
            fail(f"expected modified_files ['SKILL.md'], got {drift_payload.get('modified_files')!r}")
        if drift_payload.get('missing_files') != ['tests/smoke.md']:
            fail(f"expected missing_files ['tests/smoke.md'], got {drift_payload.get('missing_files')!r}")
        if drift_payload.get('unexpected_files') != ['local-notes.txt']:
            fail(f"expected unexpected_files ['local-notes.txt'], got {drift_payload.get('unexpected_files')!r}")

        sync_result = run(
            [str(repo / 'scripts' / 'sync-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        sync_output = sync_result.stdout + sync_result.stderr
        if 'repair-installed-skill.sh' not in sync_output or 'verify-installed-skill.py' not in sync_output:
            fail(f'expected sync drift failure to recommend verify and repair commands\n{sync_output}')

        repair_result = run(
            [str(repo / 'scripts' / 'repair-installed-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(),
        )
        repair_output = repair_result.stdout + repair_result.stderr
        if 'repaired:' not in repair_output:
            fail(f'expected repair-installed-skill.sh to report repaired output\n{repair_output}')

        repaired_payload = verify_installed_skill(repo, target_dir)
        if repaired_payload.get('state') != 'verified':
            fail(f"expected repaired install to verify cleanly, got {repaired_payload.get('state')!r}")
        if repaired_payload.get('installed_version') != VERSION:
            fail(f"expected repair to restore version {VERSION!r}, got {repaired_payload.get('installed_version')!r}")
        repaired_manifest = read_install_manifest(target_dir)
        repaired_current = ((repaired_manifest.get('skills') or {}).get(FIXTURE_NAME) or {})
        repaired_events = repaired_current.get('integrity_events')
        if not isinstance(repaired_events, list) or len(repaired_events) < 2:
            fail(f'expected repair flow to append integrity event history, got {repaired_current!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_installed_integrity_docs_exist():
    guide = ROOT / 'docs' / 'installed-skill-integrity.md'
    if not guide.exists():
        fail(f'missing installed integrity guide {guide}')
    content = guide.read_text(encoding='utf-8')
    for required in [
        'verify-installed-skill.py',
        'report-installed-integrity.py',
        '--refresh',
        'integrity_events',
        'recommended_action',
        'repair-installed-skill.sh',
        'verified',
        'drifted',
        'unknown',
    ]:
        if required not in content:
            fail(f'expected installed integrity guide to mention {required!r}')

    distribution_docs = (ROOT / 'docs' / 'distribution-manifests.md').read_text(encoding='utf-8')
    if 'repair-installed-skill.sh' not in distribution_docs:
        fail("expected docs/distribution-manifests.md to mention 'repair-installed-skill.sh'")

    compatibility_docs = (ROOT / 'docs' / 'compatibility-contract.md').read_text(encoding='utf-8')
    for required in ['integrity_capability', 'integrity_reason', 'integrity_events']:
        if required not in compatibility_docs:
            fail(f'expected docs/compatibility-contract.md to mention {required!r}')


def main():
    scenario_verify_clean_and_drifted_install()
    scenario_installed_integrity_docs_exist()
    print('OK: installed skill integrity checks passed')


if __name__ == '__main__':
    main()
