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

FIXTURE_NAME = 'release-fixture'
VERSION = '1.2.3'
SNAPSHOT_FILENAME = '.infinitas-skill-installed-integrity.json'
PLATFORM_EVIDENCE_MINUTES = {
    'codex': 0,
    'claude': 1,
    'openclaw': 2,
}


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


def make_env(repo: Path, extra=None):
    merged_extra = {'INFINITAS_SKILL_RELEASER': 'release-test'}
    if extra:
        merged_extra.update(extra)
    return build_regression_test_env(
        ROOT,
        extra=merged_extra,
        env=os.environ.copy(),
        add_pythonpath=repo / 'src',
    )


def contract_checked_at(repo: Path, platform: str):
    profile_path = repo / 'profiles' / f'{platform}.json'
    payload = json.loads(profile_path.read_text(encoding='utf-8'))
    contract = payload.get('contract') if isinstance(payload.get('contract'), dict) else {}
    last_verified = contract.get('last_verified')
    if not isinstance(last_verified, str) or not last_verified:
        fail(f'missing contract.last_verified for platform {platform!r}')
    minute = PLATFORM_EVIDENCE_MINUTES.get(platform, 0)
    return f'{last_verified}T12:{minute:02d}:00Z'


def seed_fresh_platform_evidence(repo: Path):
    fixtures = (
        ('codex', contract_checked_at(repo, 'codex')),
        ('claude', contract_checked_at(repo, 'claude')),
        ('openclaw', contract_checked_at(repo, 'openclaw')),
    )
    for platform, checked_at in fixtures:
        path = (
            repo
            / 'catalog'
            / 'compatibility-evidence'
            / platform
            / FIXTURE_NAME
            / f'{VERSION}.json'
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            path,
            {
                'platform': platform,
                'skill': FIXTURE_NAME,
                'version': VERSION,
                'state': 'adapted',
                'checked_at': checked_at,
                'checker': f'check-{platform}-compat.py',
            },
        )


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
            'summary': f'Fixture skill version {VERSION} for installed integrity report tests',
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
        'description: Fixture skill for installed integrity report tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        f'Current fixture version: {VERSION}.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'VERSION.txt').write_text(VERSION + '\n', encoding='utf-8')
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {VERSION} - 2026-03-19\n'
        '- Prepared fixture release for installed integrity report tests.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-19T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for installed integrity report tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-19T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-installed-integrity-report-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(
            '.git',
            '.venv',
            '.planning',
            '.worktrees',
            '.pytest_cache',
            '.ruff_cache',
            '.mypy_cache',
            '__pycache__',
            '*.pyc',
            '.cache',
            'scripts/__pycache__',
        ),
    )
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
        env=make_env(repo),
    )


def install_fixture(repo: Path, target_dir: Path):
    run(
        [str(repo / 'scripts' / 'install-skill.sh'), FIXTURE_NAME, str(target_dir), '--version', VERSION],
        cwd=repo,
        env=make_env(repo),
    )


def read_install_manifest(target_dir: Path):
    manifest_path = target_dir / '.infinitas-skill-install-manifest.json'
    if not manifest_path.exists():
        fail(f'missing install manifest {manifest_path}')
    return json.loads(manifest_path.read_text(encoding='utf-8'))


def run_report(repo: Path, target_dir: Path, *, refresh=False, expect=0):
    command = [
        sys.executable,
        str(repo / 'scripts' / 'report-installed-integrity.py'),
        str(target_dir),
        '--json',
    ]
    if refresh:
        command.insert(-1, '--refresh')
    result = run(command, cwd=repo, env=make_env(repo), expect=expect)
    if not result.stdout.strip():
        fail('report-installed-integrity.py did not print JSON output')
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f'report-installed-integrity.py did not emit JSON:\n{result.stdout}\n{result.stderr}\n{exc}')


def expect_single_skill_report(payload):
    skills = payload.get('skills')
    if not isinstance(skills, list) or len(skills) != 1:
        fail(f'expected one reported skill, got {payload!r}')
    item = skills[0]
    if not isinstance(item, dict):
        fail(f'expected reported skill payload to be an object, got {item!r}')
    for key in [
        'qualified_name',
        'installed_version',
        'integrity_capability',
        'recommended_action',
        'integrity_events',
        'freshness_state',
        'checked_age_seconds',
        'last_checked_at',
        'mutation_readiness',
        'mutation_policy',
        'mutation_reason_code',
        'recovery_action',
    ]:
        if key not in item:
            fail(f'expected reported skill to include {key!r}, got {item!r}')
    integrity = item.get('integrity')
    if not isinstance(integrity, dict):
        fail(f'expected reported skill integrity block, got {item!r}')
    if 'state' not in integrity:
        fail(f"expected reported integrity block to include 'state', got {item!r}")
    if not isinstance(item.get('recommended_action'), str) or not item.get('recommended_action'):
        fail(f'expected recommended_action to be a non-empty string, got {item!r}')
    if not isinstance(item.get('integrity_events'), list):
        fail(f'expected integrity_events to be a list, got {item!r}')
    return item


def scenario_report_refresh_captures_drift_and_repair_history():
    tmpdir, repo = prepare_repo()
    try:
        release_fixture(repo)
        target_dir = tmpdir / 'installed'
        target_dir.mkdir(parents=True, exist_ok=True)
        install_fixture(repo, target_dir)

        initial_report = run_report(repo, target_dir)
        initial_item = expect_single_skill_report(initial_report)
        if initial_item.get('qualified_name') != FIXTURE_NAME:
            fail(f"expected qualified_name {FIXTURE_NAME!r}, got {initial_item.get('qualified_name')!r}")
        if initial_item.get('installed_version') != VERSION:
            fail(f"expected installed_version {VERSION!r}, got {initial_item.get('installed_version')!r}")
        if (initial_item.get('integrity') or {}).get('state') != 'verified':
            fail(f"expected initial report integrity.state 'verified', got {initial_item!r}")
        if initial_item.get('integrity_capability') != 'supported':
            fail(f"expected initial integrity_capability 'supported', got {initial_item!r}")
        if not initial_item.get('last_verified_at'):
            fail(f'expected initial report to surface last_verified_at, got {initial_item!r}')
        if initial_item.get('freshness_state') != 'fresh':
            fail(f"expected initial freshness_state 'fresh', got {initial_item!r}")
        if not isinstance(initial_item.get('checked_age_seconds'), int) or initial_item.get('checked_age_seconds') < 0:
            fail(f'expected initial checked_age_seconds integer, got {initial_item!r}')
        if not isinstance(initial_item.get('last_checked_at'), str) or not initial_item.get('last_checked_at'):
            fail(f'expected initial report to surface last_checked_at, got {initial_item!r}')
        if initial_item.get('recommended_action') != 'none':
            fail(f"expected initial recommended_action 'none', got {initial_item!r}")
        if initial_item.get('mutation_readiness') != 'ready':
            fail(f"expected initial mutation_readiness 'ready', got {initial_item!r}")
        if initial_item.get('mutation_policy') is not None:
            fail(f'expected initial mutation_policy null, got {initial_item!r}')
        if initial_item.get('mutation_reason_code') is not None:
            fail(f'expected initial mutation_reason_code null, got {initial_item!r}')
        if initial_item.get('recovery_action') != 'none':
            fail(f"expected initial recovery_action 'none', got {initial_item!r}")
        initial_events = initial_item.get('integrity_events') or []
        if not initial_events:
            fail(f'expected install report to surface at least one integrity event, got {initial_item!r}')

        installed_dir = target_dir / FIXTURE_NAME
        with (installed_dir / 'SKILL.md').open('a', encoding='utf-8') as handle:
            handle.write('\nLocal drift.\n')
        (installed_dir / 'tests' / 'smoke.md').unlink()
        (installed_dir / 'local-notes.txt').write_text('temporary local note\n', encoding='utf-8')

        drift_report = run_report(repo, target_dir, refresh=True)
        drift_item = expect_single_skill_report(drift_report)
        if (drift_item.get('integrity') or {}).get('state') != 'drifted':
            fail(f"expected refresh report integrity.state 'drifted', got {drift_item!r}")
        if drift_item.get('freshness_state') != 'fresh':
            fail(f"expected drift refresh freshness_state 'fresh', got {drift_item!r}")
        if drift_item.get('recommended_action') != 'repair':
            fail(f"expected drifted recommended_action 'repair', got {drift_item!r}")
        if drift_item.get('mutation_readiness') != 'blocked':
            fail(f"expected drifted mutation_readiness 'blocked', got {drift_item!r}")
        if drift_item.get('mutation_policy') is not None:
            fail(f'expected drifted mutation_policy null, got {drift_item!r}')
        if drift_item.get('mutation_reason_code') != 'drifted-installed-skill':
            fail(f"expected drifted mutation_reason_code 'drifted-installed-skill', got {drift_item!r}")
        if drift_item.get('recovery_action') != 'repair':
            fail(f"expected drifted recovery_action 'repair', got {drift_item!r}")
        snapshot_path = target_dir / SNAPSHOT_FILENAME
        if not snapshot_path.exists():
            fail(f'expected refresh report to write installed integrity snapshot {snapshot_path}')
        drift_events = drift_item.get('integrity_events') or []
        if len(drift_events) <= len(initial_events):
            fail(f'expected refresh to append integrity event history, got {drift_item!r}')
        last_drift_event = drift_events[-1] if drift_events else {}
        if last_drift_event.get('event') != 'drifted':
            fail(f"expected last drift event 'drifted', got {drift_item!r}")
        if last_drift_event.get('source') != 'refresh':
            fail(f"expected last drift event source 'refresh', got {drift_item!r}")
        manifest = read_install_manifest(target_dir)
        manifest_item = ((manifest.get('skills') or {}).get(FIXTURE_NAME) or {})
        if ((manifest_item.get('integrity') or {}).get('state')) != 'drifted':
            fail(f"expected refreshed manifest integrity.state 'drifted', got {manifest_item!r}")
        if manifest_item.get('integrity_events') != drift_events:
            fail(f'expected refreshed manifest to persist drift event history, got {manifest_item!r}')

        repair_output = run(
            [str(repo / 'scripts' / 'repair-installed-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(repo),
        ).stdout
        if 'repaired:' not in repair_output:
            fail(f'expected repair-installed-skill.sh to report repaired output\n{repair_output}')

        repaired_report = run_report(repo, target_dir, refresh=True)
        repaired_item = expect_single_skill_report(repaired_report)
        if (repaired_item.get('integrity') or {}).get('state') != 'verified':
            fail(f"expected repaired report integrity.state 'verified', got {repaired_item!r}")
        if repaired_item.get('freshness_state') != 'fresh':
            fail(f"expected repaired freshness_state 'fresh', got {repaired_item!r}")
        if repaired_item.get('recommended_action') != 'none':
            fail(f"expected repaired recommended_action 'none', got {repaired_item!r}")
        if repaired_item.get('mutation_readiness') != 'ready':
            fail(f"expected repaired mutation_readiness 'ready', got {repaired_item!r}")
        if repaired_item.get('mutation_policy') is not None:
            fail(f'expected repaired mutation_policy null, got {repaired_item!r}')
        if repaired_item.get('mutation_reason_code') is not None:
            fail(f'expected repaired mutation_reason_code null, got {repaired_item!r}')
        if repaired_item.get('recovery_action') != 'none':
            fail(f"expected repaired recovery_action 'none', got {repaired_item!r}")
        repaired_events = repaired_item.get('integrity_events') or []
        if len(repaired_events) <= len(drift_events):
            fail(f'expected repaired refresh to append a later integrity event, got {repaired_item!r}')
        last_repaired_event = repaired_events[-1] if repaired_events else {}
        if last_repaired_event.get('event') not in {'verified', 'repaired'}:
            fail(f"expected final integrity event to be 'verified' or 'repaired', got {repaired_item!r}")
        if last_repaired_event.get('source') not in {'refresh', 'repair'}:
            fail(f"expected final integrity event source 'refresh' or 'repair', got {repaired_item!r}")
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_report_refresh_captures_drift_and_repair_history()
    print('OK: installed integrity report checks passed')


if __name__ == '__main__':
    main()
