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
    if extra:
        env.update(extra)
    return env


def scaffold_fixture(repo: Path, *, include_binary: bool = False):
    fixture_dir = repo / 'skills' / 'active' / FIXTURE_NAME
    if fixture_dir.exists():
        shutil.rmtree(fixture_dir)
    shutil.copytree(ROOT / 'templates' / 'basic-skill', fixture_dir)
    meta = json.loads((fixture_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': FIXTURE_NAME,
            'version': FIXTURE_VERSION,
            'status': 'active',
            'summary': 'Fixture skill for openclaw export tests',
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
        'description: Fixture skill for openclaw export tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated OpenClaw export tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-09\n'
        '- Added OpenClaw export fixture release.\n',
        encoding='utf-8',
    )
    if include_binary:
        (fixture_dir / 'blob.bin').write_bytes(b'\x00\x01\x02fixture-binary\x00')
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-09T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for OpenClaw export tests',
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


def prepare_repo(*, include_binary: bool = False):
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-openclaw-export-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    scaffold_fixture(repo, include_binary=include_binary)
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
    run(
        [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
        cwd=repo,
        env=make_env(),
    )
    return tmpdir, repo


def test_confirm_mode_returns_release_export_plan():
    tmpdir, repo = prepare_repo()
    try:
        out_dir = tmpdir / 'exported'
        result = run(
            [
                str(repo / 'scripts' / 'export-openclaw-skill.sh'),
                FIXTURE_NAME,
                '--version',
                FIXTURE_VERSION,
                '--out',
                str(out_dir),
                '--mode',
                'confirm',
            ],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        if payload.get('ok') is not True:
            fail(f'expected ok=true in confirm mode, got {payload!r}')
        if payload.get('state') != 'planned':
            fail(f"expected planned state, got {payload.get('state')!r}")
        export_dir = Path(payload.get('export_dir') or '').resolve()
        if export_dir != (out_dir / FIXTURE_NAME).resolve():
            fail(f'expected export_dir {(out_dir / FIXTURE_NAME).resolve()}, got {export_dir}')
        if out_dir.exists():
            fail('confirm mode unexpectedly created output directory')
        if payload.get('suggested_publish_command') != ['clawhub', 'publish', str((out_dir / FIXTURE_NAME).resolve())]:
            fail(f"unexpected publish suggestion: {payload.get('suggested_publish_command')!r}")
        if payload.get('public_ready') is not False:
            fail(f"expected confirm-mode public_ready=false without MIT-0 metadata, got {payload.get('public_ready')!r}")
        validation_errors = payload.get('validation_errors') or []
        if not any('MIT-0' in item for item in validation_errors):
            fail(f"expected confirm-mode validation errors to mention MIT-0, got {validation_errors!r}")
    finally:
        shutil.rmtree(tmpdir)


def test_auto_mode_materializes_release_bundle_as_openclaw_folder():
    tmpdir, repo = prepare_repo()
    try:
        out_dir = tmpdir / 'exported'
        result = run(
            [
                str(repo / 'scripts' / 'export-openclaw-skill.sh'),
                FIXTURE_NAME,
                '--version',
                FIXTURE_VERSION,
                '--out',
                str(out_dir),
            ],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        if payload.get('ok') is not True:
            fail(f'expected ok=true in auto mode, got {payload!r}')
        if payload.get('state') != 'exported':
            fail(f"expected exported state, got {payload.get('state')!r}")

        export_dir = out_dir / FIXTURE_NAME
        if not export_dir.is_dir():
            fail(f'missing exported skill directory {export_dir}')
        if not (export_dir / 'SKILL.md').is_file():
            fail('missing exported SKILL.md')
        if not (export_dir / '_meta.json').is_file():
            fail('missing exported _meta.json')
        skill_md = (export_dir / 'SKILL.md').read_text(encoding='utf-8')
        if 'metadata.openclaw.requires:' not in skill_md:
            fail(f'expected exported SKILL.md to include metadata.openclaw.requires\n{skill_md}')

        manifest_path = Path(payload.get('manifest_path') or '')
        bundle_path = Path(payload.get('bundle_path') or '')
        if not manifest_path.exists():
            fail(f'missing manifest path {manifest_path}')
        if not bundle_path.exists():
            fail(f'missing bundle path {bundle_path}')
        if payload.get('resolved_version') != FIXTURE_VERSION:
            fail(f"expected resolved_version {FIXTURE_VERSION!r}, got {payload.get('resolved_version')!r}")
        if payload.get('suggested_publish_command') != ['clawhub', 'publish', str(export_dir.resolve())]:
            fail(f"unexpected publish suggestion: {payload.get('suggested_publish_command')!r}")
        if payload.get('public_ready') is not False:
            fail(f"expected auto-mode public_ready=false without MIT-0 metadata, got {payload.get('public_ready')!r}")
        validation_errors = payload.get('validation_errors') or []
        if not any('MIT-0' in item for item in validation_errors):
            fail(f"expected auto-mode validation errors to mention MIT-0, got {validation_errors!r}")

        run([sys.executable, str(repo / 'scripts' / 'check-openclaw-compat.py'), '--skill-dir', str(export_dir)], cwd=repo)
    finally:
        shutil.rmtree(tmpdir)


def test_public_ready_checker_rejects_binary_exports():
    tmpdir, repo = prepare_repo(include_binary=True)
    try:
        out_dir = tmpdir / 'exported'
        run(
            [
                str(repo / 'scripts' / 'export-openclaw-skill.sh'),
                FIXTURE_NAME,
                '--version',
                FIXTURE_VERSION,
                '--out',
                str(out_dir),
            ],
            cwd=repo,
        )
        export_dir = out_dir / FIXTURE_NAME
        result = run(
            [sys.executable, str(repo / 'scripts' / 'check-openclaw-compat.py'), '--skill-dir', str(export_dir), '--public-ready'],
            cwd=repo,
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'text-only' not in combined and 'MIT-0' not in combined:
            fail(f'expected public-ready checker failure to mention text-only or MIT-0\n{combined}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    test_confirm_mode_returns_release_export_plan()
    test_auto_mode_materializes_release_bundle_as_openclaw_folder()
    test_public_ready_checker_rejects_binary_exports()
    print('OK: openclaw export checks passed')


if __name__ == '__main__':
    main()
