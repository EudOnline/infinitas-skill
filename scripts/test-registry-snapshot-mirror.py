#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


def run_cli(repo: Path, args: list[str], *, expect=0):
    env = dict(os.environ)
    pythonpath = str(repo / 'src')
    current_pythonpath = env.get('PYTHONPATH')
    env['PYTHONPATH'] = f'{pythonpath}:{current_pythonpath}' if current_pythonpath else pythonpath
    result = subprocess.run(
        [sys.executable, '-m', 'infinitas_skill.cli.main', *args],
        cwd=repo,
        text=True,
        capture_output=True,
        env=env,
    )
    if result.returncode != expect:
        fail(
            f'command {[sys.executable, "-m", "infinitas_skill.cli.main", *args]!r} '
            f'exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def copy_repo(tmpdir: Path):
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '.worktrees', '.cache', '__pycache__', 'scripts/__pycache__'),
    )
    return repo


def registry_config():
    return {
        '$schema': '../schemas/registry-sources.schema.json',
        'default_registry': 'self',
        'registries': [
            {
                'name': 'self',
                'kind': 'git',
                'url': 'https://github.com/EudOnline/infinitas-skill.git',
                'local_path': '.',
                'branch': 'main',
                'priority': 100,
                'enabled': True,
                'trust': 'private',
                'allowed_hosts': ['github.com'],
                'allowed_refs': ['refs/heads/main'],
                'pin': {
                    'mode': 'branch',
                    'value': 'main',
                },
                'update_policy': {
                    'mode': 'local-only',
                },
            },
            {
                'name': 'upstream',
                'kind': 'git',
                'url': 'https://github.com/example/upstream-skills.git',
                'priority': 80,
                'enabled': True,
                'trust': 'trusted',
                'allowed_hosts': ['github.com'],
                'allowed_refs': ['refs/tags/v1.0.0'],
                'pin': {
                    'mode': 'tag',
                    'value': 'v1.0.0',
                },
                'update_policy': {
                    'mode': 'pinned',
                },
                'refresh_policy': {
                    'interval_hours': 24,
                    'max_cache_age_hours': 72,
                    'stale_policy': 'warn',
                },
            },
        ],
    }


def registry_config_with_remote(remote_url: str):
    return {
        '$schema': '../schemas/registry-sources.schema.json',
        'default_registry': 'upstream',
        'registries': [
            {
                'name': 'self',
                'kind': 'git',
                'url': 'https://github.com/EudOnline/infinitas-skill.git',
                'local_path': '.',
                'branch': 'main',
                'priority': 100,
                'enabled': True,
                'trust': 'private',
                'allowed_hosts': ['github.com'],
                'allowed_refs': ['refs/heads/main'],
                'pin': {
                    'mode': 'branch',
                    'value': 'main',
                },
                'update_policy': {
                    'mode': 'local-only',
                },
            },
            {
                'name': 'upstream',
                'kind': 'git',
                'url': remote_url,
                'priority': 80,
                'enabled': True,
                'trust': 'trusted',
                'allowed_refs': ['refs/tags/v1.0.0'],
                'pin': {
                    'mode': 'tag',
                    'value': 'v1.0.0',
                },
                'update_policy': {
                    'mode': 'pinned',
                },
                'refresh_policy': {
                    'interval_hours': 24,
                    'max_cache_age_hours': 72,
                    'stale_policy': 'warn',
                },
            },
        ],
    }


def active_skill_meta():
    return {
        'schema_version': 1,
        'name': 'demo',
        'publisher': 'snapshot-fixture',
        'qualified_name': 'snapshot-fixture/demo',
        'version': '1.0.0',
        'status': 'active',
        'summary': 'Registry snapshot fixture skill',
        'owner': 'snapshot-fixture',
        'review_state': 'approved',
        'risk_level': 'low',
        'tests': {
            'smoke': 'tests/smoke.md',
        },
        'distribution': {
            'installable': True,
            'channel': 'git',
        },
    }


def write_skill_fixture(skill_dir: Path):
    skill_dir.mkdir(parents=True, exist_ok=True)
    write_json(skill_dir / '_meta.json', active_skill_meta())
    (skill_dir / 'SKILL.md').write_text(
        '---\nname: demo\ndescription: Snapshot fixture skill.\n---\n\n# Demo\n\nFixture skill.\n',
        encoding='utf-8',
    )
    (skill_dir / 'CHANGELOG.md').write_text('# Changelog\n\n- Initial fixture release.\n', encoding='utf-8')
    (skill_dir / 'tests' / 'smoke.md').parent.mkdir(parents=True, exist_ok=True)
    (skill_dir / 'tests' / 'smoke.md').write_text('# Smoke\n\nFixture smoke test.\n', encoding='utf-8')


def create_remote_registry_fixture(tmpdir: Path):
    remote = tmpdir / 'remote.git'
    remote_work = tmpdir / 'remote-work'
    remote_work.mkdir(parents=True, exist_ok=True)
    run(['git', 'init', '-b', 'main'], cwd=remote_work)
    run(['git', 'config', 'user.name', 'Snapshot Fixture'], cwd=remote_work)
    run(['git', 'config', 'user.email', 'snapshot@example.com'], cwd=remote_work)
    write_skill_fixture(remote_work / 'skills' / 'active' / 'demo')
    run(['git', 'add', '.'], cwd=remote_work)
    run(['git', 'commit', '-m', 'fixture'], cwd=remote_work)
    commit = run(['git', 'rev-parse', 'HEAD'], cwd=remote_work).stdout.strip()
    run(['git', 'tag', 'v1.0.0'], cwd=remote_work)
    run(['git', 'init', '--bare', str(remote)], cwd=tmpdir)
    run(['git', 'remote', 'add', 'origin', str(remote)], cwd=remote_work)
    run(['git', 'push', 'origin', 'HEAD:refs/heads/main'], cwd=remote_work)
    run(['git', 'push', 'origin', 'refs/tags/v1.0.0'], cwd=remote_work)
    return remote, commit


def write_snapshot_fixture(repo: Path):
    write_json(repo / 'config' / 'registry-sources.json', registry_config())
    snapshot_id = 'snap-20260317'
    snapshot_root = repo / '.cache' / 'registry-snapshots' / 'upstream' / snapshot_id / 'registry'
    write_skill_fixture(snapshot_root / 'skills' / 'active' / 'demo')
    metadata_path = snapshot_root.parent / 'snapshot.json'
    write_json(
        metadata_path,
        {
            'registry': 'upstream',
            'snapshot_id': snapshot_id,
            'created_at': '2026-03-17T00:00:00Z',
            'authoritative': False,
            'snapshot_root': str(snapshot_root.resolve()),
            'source_registry': {
                'name': 'upstream',
                'kind': 'git',
                'trust': 'trusted',
                'update_mode': 'pinned',
                'ref': 'refs/tags/v1.0.0',
                'tag': 'v1.0.0',
                'commit': '1234567890abcdef1234567890abcdef12345678',
            },
            'refresh_state': {
                'registry': 'upstream',
                'kind': 'git',
                'refreshed_at': '2026-03-17T00:00:00Z',
                'source_commit': '1234567890abcdef1234567890abcdef12345678',
                'source_ref': 'refs/tags/v1.0.0',
                'source_tag': 'v1.0.0',
                'cache_path': str((repo / '.cache' / 'registries' / 'upstream').resolve()),
            },
        },
    )
    return snapshot_id


def scenario_snapshot_metadata_is_visible_to_catalog_and_registry_listing():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-registry-snapshot-test-'))
    try:
        repo = copy_repo(tmpdir)
        snapshot_id = write_snapshot_fixture(repo)

        run(['bash', 'scripts/build-catalog.sh'], cwd=repo)

        registries_payload = json.loads((repo / 'catalog' / 'registries.json').read_text(encoding='utf-8'))
        registries = {item.get('name'): item for item in registries_payload.get('registries') or []}
        upstream = registries.get('upstream')
        if upstream is None:
            fail(f'expected upstream registry export, got {sorted(registries)!r}')
        if upstream.get('snapshot_count') != 1:
            fail(f'expected snapshot_count 1, got {upstream!r}')
        latest = upstream.get('latest_snapshot') or {}
        if latest.get('snapshot_id') != snapshot_id:
            fail(f'expected latest snapshot {snapshot_id!r}, got {upstream!r}')
        if latest.get('authoritative') is not False:
            fail(f'expected authoritative false for snapshot summary, got {upstream!r}')
        if latest.get('source_commit') != '1234567890abcdef1234567890abcdef12345678':
            fail(f'expected source_commit in snapshot summary, got {upstream!r}')
        available = upstream.get('available_snapshots') or []
        if len(available) != 1 or available[0].get('snapshot_id') != snapshot_id:
            fail(f'expected one available snapshot summary, got {upstream!r}')

        listed = run(['python3', 'scripts/list-registry-sources.py'], cwd=repo)
        combined = listed.stdout + listed.stderr
        if 'snapshots=1' not in combined:
            fail(f"expected registry listing to include 'snapshots=1', got {combined!r}")
        if f'latest_snapshot={snapshot_id}' not in combined:
            fail(f'expected registry listing to mention latest snapshot {snapshot_id!r}, got {combined!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_create_snapshot_from_synced_remote_registry():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-registry-snapshot-create-test-'))
    try:
        repo = copy_repo(tmpdir)
        remote, expected_commit = create_remote_registry_fixture(tmpdir)
        write_json(repo / 'config' / 'registry-sources.json', registry_config_with_remote(str(remote)))

        run(['bash', 'scripts/sync-registry-source.sh', 'upstream'], cwd=repo)

        created = run(['python3', 'scripts/create-registry-snapshot.py', 'upstream', '--json'], cwd=repo)
        payload = json.loads(created.stdout)
        if payload.get('registry') != 'upstream':
            fail(f"expected registry 'upstream', got {payload!r}")
        snapshot_id = payload.get('snapshot_id')
        if not isinstance(snapshot_id, str) or not snapshot_id:
            fail(f'expected non-empty snapshot_id, got {payload!r}')
        snapshot_root = repo / payload.get('snapshot_root')
        if not snapshot_root.exists():
            fail(f'expected snapshot_root to exist, got {payload!r}')
        metadata_path = repo / payload.get('metadata_path')
        if not metadata_path.exists():
            fail(f'expected metadata_path to exist, got {payload!r}')
        if payload.get('source_commit') != expected_commit:
            fail(f'expected source_commit {expected_commit!r}, got {payload!r}')
        if payload.get('source_tag') != 'v1.0.0':
            fail(f"expected source_tag 'v1.0.0', got {payload!r}")
        if payload.get('source_ref') != 'refs/tags/v1.0.0':
            fail(f"expected source_ref 'refs/tags/v1.0.0', got {payload!r}")
        copied_meta = snapshot_root / 'skills' / 'active' / 'demo' / '_meta.json'
        if not copied_meta.exists():
            fail(f'expected snapshot to copy the registry tree, got {payload!r}')

        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata.get('snapshot_id') != snapshot_id:
            fail(f'expected metadata snapshot_id {snapshot_id!r}, got {metadata!r}')
        if (metadata.get('source_registry') or {}).get('commit') != expected_commit:
            fail(f'expected metadata source commit {expected_commit!r}, got {metadata!r}')
        refresh_state = metadata.get('refresh_state') or {}
        if refresh_state.get('source_commit') != expected_commit:
            fail(f'expected copied refresh_state source_commit {expected_commit!r}, got {metadata!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_create_snapshot_rejects_local_only_registry():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-registry-snapshot-local-only-test-'))
    try:
        repo = copy_repo(tmpdir)
        failed = run(['python3', 'scripts/create-registry-snapshot.py', 'self', '--json'], cwd=repo, expect=1)
        combined = failed.stdout + failed.stderr
        if 'local-only' not in combined and 'remote cached git registry' not in combined:
            fail(f'expected local-only rejection, got {combined!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_create_snapshot_requires_cache_root():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-registry-snapshot-cache-test-'))
    try:
        repo = copy_repo(tmpdir)
        remote, _ = create_remote_registry_fixture(tmpdir)
        write_json(repo / 'config' / 'registry-sources.json', registry_config_with_remote(str(remote)))

        failed = run(['python3', 'scripts/create-registry-snapshot.py', 'upstream', '--json'], cwd=repo, expect=1)
        combined = failed.stdout + failed.stderr
        if 'cache root' not in combined and 'sync' not in combined:
            fail(f'expected missing cache-root error, got {combined!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_create_snapshot_requires_refresh_state_when_policy_present():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-registry-snapshot-refresh-state-test-'))
    try:
        repo = copy_repo(tmpdir)
        remote, _ = create_remote_registry_fixture(tmpdir)
        write_json(repo / 'config' / 'registry-sources.json', registry_config_with_remote(str(remote)))

        run(['bash', 'scripts/sync-registry-source.sh', 'upstream'], cwd=repo)
        refresh_state = repo / '.cache' / 'registries' / '_state' / 'upstream.json'
        if refresh_state.exists():
            refresh_state.unlink()

        failed = run(['python3', 'scripts/create-registry-snapshot.py', 'upstream', '--json'], cwd=repo, expect=1)
        combined = failed.stdout + failed.stderr
        if 'refresh state' not in combined.lower():
            fail(f'expected missing refresh-state error, got {combined!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_resolve_install_and_sync_can_use_explicit_snapshot():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-registry-snapshot-consume-test-'))
    try:
        repo = copy_repo(tmpdir)
        remote, expected_commit = create_remote_registry_fixture(tmpdir)
        write_json(repo / 'config' / 'registry-sources.json', registry_config_with_remote(str(remote)))

        run(['bash', 'scripts/sync-registry-source.sh', 'upstream'], cwd=repo)
        created = run(['python3', 'scripts/create-registry-snapshot.py', 'upstream', '--json'], cwd=repo)
        snapshot = json.loads(created.stdout)
        snapshot_id = snapshot.get('snapshot_id')
        snapshot_root = repo / snapshot.get('snapshot_root')
        if not snapshot_root.exists():
            fail(f'expected snapshot_root to exist, got {snapshot!r}')

        live_cache = repo / '.cache' / 'registries' / 'upstream'
        if live_cache.exists():
            shutil.rmtree(live_cache)

        resolved = run(
            ['python3', 'scripts/resolve-skill-source.py', 'demo', '--registry', 'upstream', '--snapshot', snapshot_id, '--json'],
            cwd=repo,
        )
        payload = json.loads(resolved.stdout)
        if payload.get('source_type') != 'registry-snapshot':
            fail(f"expected source_type 'registry-snapshot', got {payload!r}")
        if payload.get('registry_snapshot_id') != snapshot_id:
            fail(f'expected registry_snapshot_id {snapshot_id!r}, got {payload!r}')
        if payload.get('registry_snapshot_path') != snapshot.get('snapshot_root'):
            fail(f'expected registry_snapshot_path to match snapshot_root, got {payload!r}')
        if payload.get('registry_commit') != expected_commit:
            fail(f'expected registry_commit {expected_commit!r}, got {payload!r}')
        if payload.get('skill_path') != str((snapshot_root / 'skills' / 'active' / 'demo').resolve()):
            fail(f'expected skill_path to point inside the snapshot, got {payload!r}')

        missing = run(
            ['python3', 'scripts/resolve-skill-source.py', 'demo', '--registry', 'upstream', '--snapshot', 'missing-snapshot', '--json'],
            cwd=repo,
            expect=1,
        )
        missing_output = missing.stdout + missing.stderr
        if 'snapshot' not in missing_output.lower():
            fail(f'expected missing snapshot error, got {missing_output!r}')

        target_dir = repo / '.tmp-install'
        installed = run_cli(
            repo,
            [
                'install',
                'exact',
                'demo',
                str(target_dir),
                '--version',
                '1.0.0',
                '--registry',
                'upstream',
                '--snapshot',
                snapshot_id,
                '--json',
            ],
        )
        if 'synced' in (installed.stdout + installed.stderr).lower():
            pass
        manifest_path = target_dir / '.infinitas-skill-install-manifest.json'
        if not manifest_path.exists():
            fail(f'expected install manifest at {manifest_path}')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        entry = (manifest.get('skills') or {}).get('demo') or {}
        if entry.get('source_type') != 'registry-snapshot':
            fail(f"expected manifest source_type 'registry-snapshot', got {entry!r}")
        if entry.get('source_registry_snapshot_id') != snapshot_id:
            fail(f'expected manifest source_registry_snapshot_id {snapshot_id!r}, got {entry!r}')

        synced = run(['bash', 'scripts/sync-registry-source.sh', 'upstream', '--snapshot', snapshot_id], cwd=repo)
        synced_path = synced.stdout.strip()
        if synced_path != str(snapshot_root.resolve()):
            fail(f'expected snapshot sync to print {snapshot_root.resolve()!s}, got {synced_path!r}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_snapshot_metadata_is_visible_to_catalog_and_registry_listing()
    scenario_create_snapshot_from_synced_remote_registry()
    scenario_create_snapshot_rejects_local_only_registry()
    scenario_create_snapshot_requires_cache_root()
    scenario_create_snapshot_requires_refresh_state_when_policy_present()
    scenario_resolve_install_and_sync_can_use_explicit_snapshot()
    print('OK: registry snapshot mirror checks passed')


if __name__ == '__main__':
    main()
