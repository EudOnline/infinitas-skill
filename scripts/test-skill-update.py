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
V1 = '1.2.3'
V2 = '1.2.4'


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


def scaffold_fixture(repo: Path, version: str):
    fixture_dir = repo / 'skills' / 'active' / FIXTURE_NAME
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    shutil.copytree(ROOT / 'templates' / 'basic-skill', fixture_dir)
    update_fixture(repo, version)


def update_fixture(repo: Path, version: str):
    fixture_dir = repo / 'skills' / 'active' / FIXTURE_NAME
    meta = json.loads((fixture_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': FIXTURE_NAME,
            'version': version,
            'status': 'active',
            'summary': f'Fixture skill version {version} for skill update tests',
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
        'description: Fixture skill for skill update tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        f'Current fixture version: {version}.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'VERSION.txt').write_text(version + '\n', encoding='utf-8')
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {version} - 2026-03-12\n'
        f'- Prepared update fixture for {version}.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-12T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for skill update tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-12T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-skill-update-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    scaffold_fixture(repo, V1)
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


def release_current(repo: Path, version: str):
    run(
        [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
        cwd=repo,
        env=make_env(),
    )
    manifest = repo / 'catalog' / 'distributions' / '_legacy' / FIXTURE_NAME / version / 'manifest.json'
    if not manifest.exists():
        fail(f'missing distribution manifest {manifest}')
    return manifest


def commit_fixture_version(repo: Path, version: str):
    update_fixture(repo, version)
    run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
    run(['git', 'add', 'skills/active/' + FIXTURE_NAME, 'catalog'], cwd=repo)
    run(['git', 'commit', '-m', f'fixture {version}'], cwd=repo)
    run(['git', 'push'], cwd=repo)


def read_install_manifest(target_dir: Path):
    manifest = target_dir / '.infinitas-skill-install-manifest.json'
    if not manifest.exists():
        fail(f'missing install manifest {manifest}')
    return json.loads(manifest.read_text(encoding='utf-8'))


def main():
    tmpdir, repo = prepare_repo()
    try:
        release_current(repo, V1)
        commit_fixture_version(repo, V2)
        release_current(repo, V2)
        shutil.rmtree(repo / 'skills' / 'active' / FIXTURE_NAME)

        target_dir = tmpdir / 'installed'
        run([str(repo / 'scripts' / 'install-by-name.sh'), FIXTURE_NAME, str(target_dir), '--version', V1], cwd=repo)

        payload = json.loads(run([str(repo / 'scripts' / 'check-skill-update.sh'), FIXTURE_NAME, str(target_dir)], cwd=repo).stdout)
        if payload.get('installed_version') != V1:
            fail(f"expected installed_version {V1!r}, got {payload.get('installed_version')!r}")
        if payload.get('latest_available_version') != V2:
            fail(f"expected latest_available_version {V2!r}, got {payload.get('latest_available_version')!r}")
        if payload.get('update_available') is not True:
            fail(f"expected update_available true, got {payload.get('update_available')!r}")
        if payload.get('source_registry') != 'self':
            fail(f"expected source_registry self, got {payload.get('source_registry')!r}")
        integrity = payload.get('integrity')
        if not isinstance(integrity, dict):
            fail(f'expected integrity object in check-skill-update payload, got {integrity!r}')
        if integrity.get('state') != 'verified':
            fail(f"expected integrity.state 'verified', got {integrity.get('state')!r}")
        if not integrity.get('last_verified_at'):
            fail('expected integrity.last_verified_at to be populated')

        installed_dir = target_dir / FIXTURE_NAME
        with (installed_dir / 'SKILL.md').open('a', encoding='utf-8') as handle:
            handle.write('\nLocal drift before update check.\n')

        payload = json.loads(run([str(repo / 'scripts' / 'check-skill-update.sh'), FIXTURE_NAME, str(target_dir)], cwd=repo).stdout)
        if payload.get('update_available') is not True:
            fail(f"expected update_available true for drifted install, got {payload.get('update_available')!r}")
        integrity = payload.get('integrity')
        if not isinstance(integrity, dict):
            fail(f'expected integrity object after drift, got {integrity!r}')
        if integrity.get('state') != 'drifted':
            fail(f"expected integrity.state 'drifted', got {integrity.get('state')!r}")
        if 'SKILL.md' not in (integrity.get('modified_files') or []):
            fail(f"expected integrity.modified_files to include 'SKILL.md', got {integrity.get('modified_files')!r}")

        result = run(
            [str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'repair-installed-skill.sh' not in combined or 'verify-installed-skill.py' not in combined:
            fail(f'expected drifted upgrade failure to recommend verify and repair commands\n{combined}')

        repair_result = run(
            [str(repo / 'scripts' / 'repair-installed-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(),
        )
        repair_output = repair_result.stdout + repair_result.stderr
        if 'repaired:' not in repair_output:
            fail(f'expected repair-installed-skill.sh to report repaired output\n{repair_output}')
        manifest = read_install_manifest(target_dir)
        current = ((manifest.get('skills') or {}).get(FIXTURE_NAME) or {})
        if current.get('installed_version') != V1:
            fail(f"expected repair to restore recorded version {V1!r}, got {current.get('installed_version')!r}")

        payload = json.loads(run([str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir)], cwd=repo).stdout)
        if payload.get('from_version') != V1:
            fail(f"expected from_version {V1!r}, got {payload.get('from_version')!r}")
        if payload.get('to_version') != V2:
            fail(f"expected to_version {V2!r}, got {payload.get('to_version')!r}")
        manifest = read_install_manifest(target_dir)
        current = ((manifest.get('skills') or {}).get(FIXTURE_NAME) or {})
        if current.get('installed_version') != V2:
            fail(f"expected installed_version {V2!r} after upgrade, got {current.get('installed_version')!r}")
        history = (manifest.get('history') or {}).get(FIXTURE_NAME) or []
        if len(history) < 1:
            fail('expected upgrade to preserve at least one history entry')

        installed_dir = target_dir / FIXTURE_NAME
        with (installed_dir / 'SKILL.md').open('a', encoding='utf-8') as handle:
            handle.write('\nLocal drift before rollback.\n')

        result = run(
            [str(repo / 'scripts' / 'rollback-installed-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'repair-installed-skill.sh' not in combined or 'verify-installed-skill.py' not in combined:
            fail(f'expected drifted rollback failure to recommend verify and repair commands\n{combined}')

        run(
            [str(repo / 'scripts' / 'repair-installed-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(),
        )

        result = run(
            [str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir), '--registry', 'other-registry'],
            cwd=repo,
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'cross-source-upgrade-not-allowed' not in combined:
            fail(f'expected cross-source-upgrade-not-allowed in failure output\n{combined}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: skill update checks passed')


if __name__ == '__main__':
    main()
