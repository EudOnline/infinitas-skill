#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACTIVE_NAME = 'release-fixture'
INCUBATING_NAME = 'needs-review'
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
    if extra:
        env.update(extra)
    return env


def scaffold_skill(repo: Path, stage: str, name: str, approved: bool):
    skill_dir = repo / 'skills' / stage / name
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    shutil.copytree(ROOT / 'templates' / 'basic-skill', skill_dir)
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': name,
            'version': FIXTURE_VERSION,
            'status': stage,
            'summary': f'{name} fixture for ai publish tests',
            'owner': 'release-test',
            'owners': ['release-test'],
            'author': 'release-test',
            'review_state': 'approved' if approved else 'draft',
        }
    )
    write_json(skill_dir / '_meta.json', meta)
    (skill_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {name}\n'
        f'description: Fixture skill {name} for ai publish tests.\n'
        '---\n\n'
        f'# {name}\n\n'
        'Used only by automated AI publish tests.\n',
        encoding='utf-8',
    )
    (skill_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-09\n'
        f'- Added {name} AI publish fixture.\n',
        encoding='utf-8',
    )
    reviews = {'version': 1, 'requests': [], 'entries': []}
    if approved:
        reviews = {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-09T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for AI publish tests',
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
        }
    write_json(skill_dir / 'reviews.json', reviews)


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-ai-publish-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    scaffold_skill(repo, 'active', ACTIVE_NAME, approved=True)
    scaffold_skill(repo, 'incubating', INCUBATING_NAME, approved=False)
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


def main():
    tmpdir, repo = prepare_repo()
    try:
        preview = run([str(repo / 'scripts' / 'publish-skill.sh'), ACTIVE_NAME, '--mode', 'confirm'], cwd=repo)
        preview_payload = json.loads(preview.stdout)
        if preview_payload.get('state') != 'planned':
            fail(f"expected planned state, got {preview_payload.get('state')!r}")
        preview_manifest = repo / preview_payload['manifest_path']
        if preview_manifest.exists():
            fail('confirm mode unexpectedly created manifest before publish')

        result = run([str(repo / 'scripts' / 'publish-skill.sh'), ACTIVE_NAME], cwd=repo, env=make_env())
        payload = json.loads(result.stdout)
        if payload.get('ok') is not True:
            fail(f'expected publish ok=true, got {payload!r}')
        if payload.get('state') != 'published':
            fail(f"expected published state, got {payload.get('state')!r}")
        manifest_path = repo / payload['manifest_path']
        if not manifest_path.exists():
            fail(f'missing manifest {manifest_path}')
        attestation_path = repo / payload['attestation_path']
        if not attestation_path.exists():
            fail(f'missing attestation {attestation_path}')

        run([str(repo / 'scripts' / 'publish-skill.sh'), INCUBATING_NAME], cwd=repo, expect=1, env=make_env())
    finally:
        shutil.rmtree(tmpdir)

    print('OK: ai publish checks passed')


if __name__ == '__main__':
    main()
