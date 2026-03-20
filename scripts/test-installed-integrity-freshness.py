#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def iso_hours_ago(hours: int):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-installed-integrity-freshness-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    write_json(
        repo / 'config' / 'install-integrity-policy.json',
        {
            '$schema': '../schemas/install-integrity-policy.schema.json',
            'schema_version': 1,
            'freshness': {
                'stale_after_hours': 24,
            },
            'history': {
                'max_inline_events': 5,
            },
        },
    )
    return tmpdir, repo


def prepare_target(repo: Path):
    target = repo / '.tmp-installed-freshness'
    target.mkdir(parents=True, exist_ok=True)
    skill_dir = target / 'demo-skill'
    shutil.copytree(repo / 'templates' / 'basic-skill', skill_dir)
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': 'demo-skill',
            'version': '1.2.3',
            'status': 'active',
            'summary': 'Demo installed skill for freshness tests',
            'owner': 'freshness-test',
            'owners': ['freshness-test'],
            'author': 'freshness-test',
            'review_state': 'approved',
        }
    )
    write_json(skill_dir / '_meta.json', meta)
    manifest = {
        'schema_version': 1,
        'repo': 'https://example.invalid/repo.git',
        'updated_at': iso_hours_ago(1),
        'skills': {
            'demo-skill': {
                'name': 'demo-skill',
                'qualified_name': 'demo-skill',
                'version': '1.2.3',
                'installed_version': '1.2.3',
                'locked_version': '1.2.3',
                'source_registry': 'self',
                'target_path': 'demo-skill',
                'action': 'install',
                'integrity': {
                    'state': 'verified',
                    'last_verified_at': iso_hours_ago(2),
                },
                'last_checked_at': iso_hours_ago(2),
            },
            'stale-skill': {
                'name': 'stale-skill',
                'qualified_name': 'stale-skill',
                'version': '2.0.0',
                'installed_version': '2.0.0',
                'locked_version': '2.0.0',
                'source_registry': 'self',
                'target_path': 'stale-skill',
                'action': 'install',
                'integrity': {
                    'state': 'verified',
                    'last_verified_at': iso_hours_ago(72),
                },
                'last_checked_at': iso_hours_ago(72),
            },
            'legacy-skill': {
                'name': 'legacy-skill',
                'qualified_name': 'legacy-skill',
                'version': '0.9.0',
                'installed_version': '0.9.0',
                'locked_version': '0.9.0',
                'source_registry': 'self',
                'target_path': 'legacy-skill',
                'action': 'install',
                'integrity': {
                    'state': 'unknown',
                },
            },
            'drifted-skill': {
                'name': 'drifted-skill',
                'qualified_name': 'drifted-skill',
                'version': '3.0.0',
                'installed_version': '3.0.0',
                'locked_version': '3.0.0',
                'source_registry': 'self',
                'target_path': 'drifted-skill',
                'action': 'install',
                'integrity': {
                    'state': 'drifted',
                    'last_verified_at': iso_hours_ago(72),
                },
                'last_checked_at': iso_hours_ago(72),
            },
        },
        'history': {},
    }
    write_json(target / '.infinitas-skill-install-manifest.json', manifest)
    return target


def report_map(payload):
    skills = payload.get('skills')
    if not isinstance(skills, list):
        fail(f'expected report payload skills list, got {payload!r}')
    return {item.get('name') or item.get('qualified_name'): item for item in skills if isinstance(item, dict)}


def main():
    tmpdir, repo = prepare_repo()
    try:
        target = prepare_target(repo)
        result = run(
            [sys.executable, str(repo / 'scripts' / 'report-installed-integrity.py'), str(target), '--json'],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        items = report_map(payload)
        listed = run([str(repo / 'scripts' / 'list-installed.sh'), str(target)], cwd=repo).stdout
        for required in ['freshness=fresh', 'freshness=stale', 'freshness=never-verified']:
            if required not in listed:
                fail(f'expected list-installed output to surface {required!r}\n{listed}')

        fresh = items.get('demo-skill')
        if fresh is None:
            fail(f'missing fresh report item: {payload!r}')
        if fresh.get('freshness_state') != 'fresh':
            fail(f"expected freshness_state 'fresh', got {fresh!r}")
        if not isinstance(fresh.get('checked_age_seconds'), int) or fresh.get('checked_age_seconds') < 0:
            fail(f'expected checked_age_seconds integer for fresh item, got {fresh!r}')
        if not isinstance(fresh.get('last_checked_at'), str) or not fresh.get('last_checked_at'):
            fail(f'expected last_checked_at string for fresh item, got {fresh!r}')
        if fresh.get('recommended_action') != 'none':
            fail(f"expected fresh recommended_action 'none', got {fresh!r}")
        if fresh.get('mutation_readiness') != 'ready':
            fail(f"expected fresh mutation_readiness 'ready', got {fresh!r}")
        if fresh.get('mutation_policy') is not None:
            fail(f'expected fresh mutation_policy null, got {fresh!r}')
        if fresh.get('mutation_reason_code') is not None:
            fail(f'expected fresh mutation_reason_code null, got {fresh!r}')
        if fresh.get('recovery_action') != 'none':
            fail(f"expected fresh recovery_action 'none', got {fresh!r}")

        stale = items.get('stale-skill')
        if stale is None:
            fail(f'missing stale report item: {payload!r}')
        if stale.get('freshness_state') != 'stale':
            fail(f"expected freshness_state 'stale', got {stale!r}")
        if stale.get('recommended_action') != 'refresh':
            fail(f"expected stale recommended_action 'refresh', got {stale!r}")
        if stale.get('mutation_readiness') != 'warning':
            fail(f"expected stale mutation_readiness 'warning', got {stale!r}")
        if stale.get('mutation_policy') != 'warn':
            fail(f"expected stale mutation_policy 'warn', got {stale!r}")
        if stale.get('mutation_reason_code') != 'stale-installed-integrity':
            fail(f"expected stale mutation_reason_code 'stale-installed-integrity', got {stale!r}")
        if stale.get('recovery_action') != 'refresh':
            fail(f"expected stale recovery_action 'refresh', got {stale!r}")

        legacy = items.get('legacy-skill')
        if legacy is None:
            fail(f'missing legacy report item: {payload!r}')
        if legacy.get('freshness_state') != 'never-verified':
            fail(f"expected freshness_state 'never-verified', got {legacy!r}")
        if legacy.get('checked_age_seconds') is not None:
            fail(f'expected legacy checked_age_seconds null, got {legacy!r}')
        if legacy.get('last_checked_at') is not None:
            fail(f'expected legacy last_checked_at null, got {legacy!r}')
        if legacy.get('mutation_readiness') != 'warning':
            fail(f"expected legacy mutation_readiness 'warning', got {legacy!r}")
        if legacy.get('mutation_policy') != 'warn':
            fail(f"expected legacy mutation_policy 'warn', got {legacy!r}")
        if legacy.get('mutation_reason_code') != 'never-verified-installed-integrity':
            fail(f"expected legacy mutation_reason_code 'never-verified-installed-integrity', got {legacy!r}")
        if legacy.get('recovery_action') != 'reinstall':
            fail(f"expected legacy recovery_action 'reinstall', got {legacy!r}")

        drifted = items.get('drifted-skill')
        if drifted is None:
            fail(f'missing drifted report item: {payload!r}')
        if drifted.get('freshness_state') != 'stale':
            fail(f"expected drifted freshness_state 'stale', got {drifted!r}")
        if drifted.get('recommended_action') != 'repair':
            fail(f"expected drifted recommended_action 'repair', got {drifted!r}")
        if drifted.get('mutation_readiness') != 'blocked':
            fail(f"expected drifted mutation_readiness 'blocked', got {drifted!r}")
        if drifted.get('mutation_policy') is not None:
            fail(f'expected drifted mutation_policy null, got {drifted!r}')
        if drifted.get('mutation_reason_code') != 'drifted-installed-skill':
            fail(f"expected drifted mutation_reason_code 'drifted-installed-skill', got {drifted!r}")
        if drifted.get('recovery_action') != 'repair':
            fail(f"expected drifted recovery_action 'repair', got {drifted!r}")
    finally:
        shutil.rmtree(tmpdir)

    print('OK: installed integrity freshness checks passed')


if __name__ == '__main__':
    main()
