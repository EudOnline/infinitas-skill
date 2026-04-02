#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.testing.env import build_regression_test_env

FIXTURE_NAME = 'bootstrap-fixture'
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
    return build_regression_test_env(ROOT, extra=extra, env=os.environ.copy())


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
            'summary': 'Fixture skill for signing readiness reporting',
            'owner': 'lvxiaoer',
            'owners': ['lvxiaoer'],
            'maintainers': ['lvxiaoer'],
            'author': 'release-test',
            'review_state': 'approved',
        }
    )
    write_json(fixture_dir / '_meta.json', meta)
    (fixture_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {FIXTURE_NAME}\n'
        'description: Fixture skill for signing readiness reporting.\n'
        '---\n\n'
        '# Signing Readiness Fixture\n\n'
        'Used only by automated signing readiness tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-16\n'
        '- Added signing readiness reporting fixture.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-16T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for signing readiness reporting',
                }
            ],
            'entries': [
                {
                    'reviewer': 'alice',
                    'decision': 'approved',
                    'at': '2026-03-16T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def seed_fresh_platform_evidence(repo: Path):
    fixtures = [
        ('codex', '2026-03-12T12:00:00Z'),
        ('claude', '2026-03-12T12:01:00Z'),
        ('openclaw', '2026-03-12T12:02:00Z'),
    ]
    for platform, checked_at in fixtures:
        path = repo / 'catalog' / 'compatibility-evidence' / platform / FIXTURE_NAME / f'{FIXTURE_VERSION}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            path,
            {
                'platform': platform,
                'skill': FIXTURE_NAME,
                'version': FIXTURE_VERSION,
                'state': 'adapted',
                'checked_at': checked_at,
                'checker': f'check-{platform}-compat.py',
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
                    'at': '2026-03-16T00:10:00Z',
                    'note': f'Fixture-compatible approval for active skill {skill_dir.name}',
                }
            )
        reviews['entries'] = entries
        write_json(reviews_path, reviews)


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-signing-readiness-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    rewrite_promotion_policy(repo)
    (repo / 'config' / 'allowed_signers').write_text('', encoding='utf-8')
    stabilize_active_skill_reviews(repo)
    scaffold_fixture(repo)
    seed_fresh_platform_evidence(repo)
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
    return tmpdir, repo


def bootstrap_release(repo: Path, tmpdir: Path):
    key_path = tmpdir / 'release-test-key'
    env = make_env()
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'init-key',
            '--identity',
            'release-test',
            '--output',
            str(key_path),
        ],
        cwd=repo,
        env=env,
    )
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'add-allowed-signer',
            '--identity',
            'release-test',
            '--key',
            str(key_path),
        ],
        cwd=repo,
        env=env,
    )
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'configure-git',
            '--key',
            str(key_path),
        ],
        cwd=repo,
        env=env,
    )
    run(
        [
            sys.executable,
            str(repo / 'scripts' / 'bootstrap-signing.py'),
            'authorize-publisher',
            '--publisher',
            'lvxiaoer',
            '--signer',
            'release-test',
            '--releaser',
            'Release Fixture',
        ],
        cwd=repo,
        env=env,
    )
    run(['git', 'add', 'config/allowed_signers', 'policy/namespace-policy.json'], cwd=repo)
    run(['git', 'commit', '-m', 'bootstrap release signer'], cwd=repo)
    run(['git', 'push'], cwd=repo)
    run(
        [
            str(repo / 'scripts' / 'release-skill.sh'),
            FIXTURE_NAME,
            '--push-tag',
            '--notes-out',
            str(tmpdir / 'fixture-release-notes.md'),
            '--write-provenance',
        ],
        cwd=repo,
        env=env,
    )


def load_report(repo: Path, env=None):
    result = run(
        [
            sys.executable,
            str(repo / 'scripts' / 'report-signing-readiness.py'),
            '--skill',
            FIXTURE_NAME,
            '--json',
        ],
        cwd=repo,
        env=env,
    )
    return json.loads(result.stdout)


def assert_signing_docs_synced(repo: Path):
    stale_phrases = {
        '.planning/PROJECT.md': [
            'Bootstrap real trusted signer entries in `config/allowed_signers` before the first production stable release ceremony.',
            '`config/allowed_signers` is still intentionally bootstrapped with guidance comments only; maintainers must commit real trusted signer entries before the first actual stable release is operationally complete.',
        ],
        '.planning/STATE.md': [
            'Bootstrap real trusted signer entries in `config/allowed_signers` before the first actual stable release.',
            '`config/allowed_signers` still contains bootstrap guidance comments only; the bootstrap and doctor flow exist, but a real production signer ceremony is still pending.',
        ],
        'docs/ops/signing-bootstrap.md': [
            '`config/allowed_signers` intentionally starts with comments only.',
        ],
    }
    required_phrases = {
        'docs/ops/signing-bootstrap.md': [
            'uv run infinitas release signing-readiness --skill my-skill --json',
            'This repository is already bootstrapped with a committed `lvxiaoer` signer entry',
        ],
        'docs/ops/signing-operations.md': [
            '# Signing Operations',
            'uv run infinitas release signing-readiness --skill operate-infinitas-skill --json',
        ],
        '.planning/PROJECT.md': [
            '`config/allowed_signers` now contains a committed `lvxiaoer` trusted signer entry.',
        ],
        '.planning/STATE.md': [
            '`operate-infinitas-skill` already has a signed pushed stable tag plus verified provenance.',
        ],
    }

    for relative_path, phrases in stale_phrases.items():
        text = (repo / relative_path).read_text(encoding='utf-8')
        for phrase in phrases:
            if phrase in text:
                fail(f'{relative_path} still contains stale signer text: {phrase!r}')

    for relative_path, phrases in required_phrases.items():
        text = (repo / relative_path).read_text(encoding='utf-8')
        for phrase in phrases:
            if phrase not in text:
                fail(f'{relative_path} is missing required signer readiness text: {phrase!r}')


def scenario_reports_pending_and_ready_states():
    tmpdir, repo = prepare_repo()
    try:
        pending = load_report(repo, env=make_env())
        if pending.get('overall_status') != 'warn':
            fail(f"expected pending overall_status 'warn', got {pending.get('overall_status')!r}")
        trusted_signers = pending.get('trusted_signers') or {}
        if trusted_signers.get('count') != 0:
            fail(f'expected zero trusted signers before bootstrap, got {trusted_signers!r}')
        skills = pending.get('skills') or []
        if len(skills) != 1:
            fail(f'expected one reported skill before bootstrap, got {skills!r}')
        pending_skill = skills[0]
        if pending_skill.get('release_ready') is not False:
            fail(f'expected pending release_ready false, got {pending_skill!r}')
        if (pending_skill.get('tag') or {}).get('present') is not False:
            fail(f'expected pending tag absent, got {pending_skill!r}')
        if (pending_skill.get('provenance') or {}).get('verified') is not False:
            fail(f'expected pending provenance unverified, got {pending_skill!r}')

        bootstrap_release(repo, tmpdir)

        ready = load_report(repo, env=make_env())
        if ready.get('overall_status') != 'ok':
            fail(f"expected ready overall_status 'ok', got {ready.get('overall_status')!r}")
        ready_trusted_signers = ready.get('trusted_signers') or {}
        if ready_trusted_signers.get('count') != 1:
            fail(f'expected one trusted signer after bootstrap, got {ready_trusted_signers!r}')
        if ready_trusted_signers.get('identities') != ['release-test']:
            fail(f'expected release-test signer identity, got {ready_trusted_signers!r}')
        ready_skill = (ready.get('skills') or [None])[0]
        if not ready_skill:
            fail(f'missing ready skill payload: {ready!r}')
        if ready_skill.get('release_ready') is not True:
            fail(f'expected release_ready true after bootstrap, got {ready_skill!r}')
        if (ready_skill.get('tag') or {}).get('present') is not True:
            fail(f'expected ready tag present, got {ready_skill!r}')
        if (ready_skill.get('tag') or {}).get('verified') is not True:
            fail(f'expected ready tag verified, got {ready_skill!r}')
        if (ready_skill.get('provenance') or {}).get('verified') is not True:
            fail(f'expected ready provenance verified, got {ready_skill!r}')
        assert_signing_docs_synced(repo)
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_reports_pending_and_ready_states()
    print('OK: signing readiness reporting checks passed')


if __name__ == '__main__':
    main()
