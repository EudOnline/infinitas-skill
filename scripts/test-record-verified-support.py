#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_NAME = 'verified-support-fixture'
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
    env['INFINITAS_SKIP_COMPAT_PIPELINE_TESTS'] = '1'
    env['INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS'] = '1'
    env['INFINITAS_SKIP_RELEASE_TESTS'] = '1'
    env['INFINITAS_SKIP_ATTESTATION_TESTS'] = '1'
    env['INFINITAS_SKIP_DISTRIBUTION_TESTS'] = '1'
    env['INFINITAS_SKIP_BOOTSTRAP_TESTS'] = '1'
    env['INFINITAS_SKIP_AI_WRAPPER_TESTS'] = '1'
    env['INFINITAS_SKIP_RECORD_VERIFIED_SUPPORT_TESTS'] = '1'
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
            'publisher': 'lvxiaoer',
            'qualified_name': f'lvxiaoer/{FIXTURE_NAME}',
            'version': FIXTURE_VERSION,
            'status': 'active',
            'summary': 'Fixture skill for verified support recording',
            'owner': 'lvxiaoer',
            'owners': ['lvxiaoer'],
            'author': 'verified-test',
            'maintainers': ['lvxiaoer'],
            'review_state': 'approved',
            'risk_level': 'low',
            'agent_compatible': ['claude', 'codex', 'openclaw'],
        }
    )
    write_json(fixture_dir / '_meta.json', meta)
    (fixture_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {FIXTURE_NAME}\n'
        'description: Fixture skill for verified support recording.\n'
        '---\n\n'
        '# Verified Support Fixture\n\n'
        'Used only by automated verified-support tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-12\n'
        '- Added verified support fixture release.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-12T00:00:00Z',
                    'requested_by': 'verified-test',
                    'note': 'Fixture approval for verified support recording',
                }
            ],
            'entries': [
                {
                    'reviewer': 'alice',
                    'decision': 'approved',
                    'at': '2026-03-12T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def rewrite_promotion_policy(repo: Path):
    policy_path = repo / 'policy' / 'promotion-policy.json'
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    reviews = policy.get('reviews') if isinstance(policy.get('reviews'), dict) else {}
    groups = reviews.get('groups') if isinstance(reviews.get('groups'), dict) else {}
    maintainers = groups.get('maintainers') if isinstance(groups.get('maintainers'), dict) else {}
    members = maintainers.get('members') if isinstance(maintainers.get('members'), list) else []
    maintainers['members'] = list(dict.fromkeys([*members, 'alice']))
    groups['maintainers'] = maintainers
    reviews['groups'] = groups
    policy['reviews'] = reviews
    write_json(policy_path, policy)


def stabilize_active_skill_reviews(repo: Path):
    active_root = repo / 'skills' / 'active'
    if not active_root.is_dir():
        return
    for skill_dir in sorted(path for path in active_root.iterdir() if path.is_dir()):
        reviews_path = skill_dir / 'reviews.json'
        reviews = (
            json.loads(reviews_path.read_text(encoding='utf-8'))
            if reviews_path.exists()
            else {'version': 1, 'requests': [], 'entries': []}
        )
        entries = reviews.get('entries') if isinstance(reviews.get('entries'), list) else []
        if not any(item.get('reviewer') == 'alice' and item.get('decision') == 'approved' for item in entries):
            entries.append(
                {
                    'reviewer': 'alice',
                    'decision': 'approved',
                    'at': '2026-03-12T00:10:00Z',
                    'note': f'Fixture-compatible approval for active skill {skill_dir.name}',
                }
            )
        reviews['entries'] = entries
        write_json(reviews_path, reviews)


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-record-verified-support-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    rewrite_promotion_policy(repo)
    stabilize_active_skill_reviews(repo)
    scaffold_fixture(repo)
    run(['git', 'init', '--bare', str(origin)], cwd=tmpdir)
    run(['git', 'init', '-b', 'main'], cwd=repo)
    run(['git', 'config', 'user.name', 'Verified Fixture'], cwd=repo)
    run(['git', 'config', 'user.email', 'verified@example.com'], cwd=repo)
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


def main():
    tmpdir, repo = prepare_repo()
    try:
        run(
            [
                sys.executable,
                str(repo / 'scripts' / 'record-verified-support.py'),
                FIXTURE_NAME,
                '--platform',
                'codex',
                '--platform',
                'claude',
                '--platform',
                'openclaw',
                '--build-catalog',
            ],
            cwd=repo,
        )

        for platform in ['codex', 'claude', 'openclaw']:
            path = repo / 'catalog' / 'compatibility-evidence' / platform / FIXTURE_NAME / f'{FIXTURE_VERSION}.json'
            if not path.is_file():
                fail(f'missing compatibility evidence file {path}')
            payload = json.loads(path.read_text(encoding='utf-8'))
            if payload.get('state') != 'adapted':
                fail(f"expected adapted evidence state for {platform}, got {payload.get('state')!r}")

        compatibility = json.loads((repo / 'catalog' / 'compatibility.json').read_text(encoding='utf-8'))
        entry = next((item for item in compatibility.get('skills', []) if item.get('name') == FIXTURE_NAME), None)
        if entry is None:
            fail(f'missing compatibility entry for {FIXTURE_NAME}')

        verified = entry.get('verified_support') or {}
        for platform in ['codex', 'claude', 'openclaw']:
            if verified.get(platform, {}).get('state') != 'adapted':
                fail(f"expected verified_support {platform}=adapted, got {verified.get(platform)!r}")

        distributions = json.loads((repo / 'catalog' / 'distributions.json').read_text(encoding='utf-8'))
        if distributions.get('count', 0) < 1:
            fail(f'expected non-empty distributions catalog, got {distributions!r}')

        ai_index = json.loads((repo / 'catalog' / 'ai-index.json').read_text(encoding='utf-8'))
        skills = ai_index.get('skills') or []
        if not any(item.get('name') == FIXTURE_NAME for item in skills):
            fail(f'expected ai-index to contain {FIXTURE_NAME}, got {skills!r}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: verified support recording checks passed')


if __name__ == '__main__':
    main()
