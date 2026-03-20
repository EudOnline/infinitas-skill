#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
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


def iso_hours_ago(hours: int):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


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
            'summary': f'Fixture skill version {version} for distribution tests',
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
        'description: Fixture skill for distribution manifest tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        f'Current fixture version: {version}.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'VERSION.txt').write_text(version + '\n', encoding='utf-8')
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {version} - 2026-03-09\n'
        f'- Prepared immutable distribution bundle for {version}.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-09T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for distribution tests',
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


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-distribution-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
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


def write_install_manifest(target_dir: Path, payload):
    write_json(target_dir / '.infinitas-skill-install-manifest.json', payload)


def write_install_integrity_policy(
    repo: Path,
    *,
    stale_policy: str,
    never_verified_policy: str | None = None,
    stale_after_hours: int = 24,
    max_inline_events: int = 20,
):
    freshness = {
        'stale_after_hours': stale_after_hours,
        'stale_policy': stale_policy,
    }
    if never_verified_policy is not None:
        freshness['never_verified_policy'] = never_verified_policy
    write_json(
        repo / 'config' / 'install-integrity-policy.json',
        {
            '$schema': '../schemas/install-integrity-policy.schema.json',
            'schema_version': 1,
            'freshness': freshness,
            'history': {
                'max_inline_events': max_inline_events,
            },
        },
    )


def mark_install_stale(target_dir: Path, name: str, *, hours_ago: int = 72):
    payload = read_install_manifest(target_dir)
    current = ((payload.get('skills') or {}).get(name) or {})
    stale_at = iso_hours_ago(hours_ago)
    current['last_checked_at'] = stale_at
    integrity = dict(current.get('integrity') or {})
    integrity['state'] = 'verified'
    integrity['last_verified_at'] = stale_at
    current['integrity'] = integrity
    payload['skills'][name] = current
    write_install_manifest(target_dir, payload)


def mark_install_never_verified(target_dir: Path, name: str):
    payload = read_install_manifest(target_dir)
    current = ((payload.get('skills') or {}).get(name) or {})
    current.pop('last_checked_at', None)
    integrity = dict(current.get('integrity') or {})
    integrity['state'] = 'verified'
    integrity.pop('last_verified_at', None)
    current['integrity'] = integrity
    payload['skills'][name] = current
    write_install_manifest(target_dir, payload)


def assert_current_install(target_dir: Path, version: str, *, source_type='distribution-manifest'):
    manifest = read_install_manifest(target_dir)
    meta = (manifest.get('skills') or {}).get(FIXTURE_NAME)
    if not isinstance(meta, dict):
        fail(f'missing installed skill entry for {FIXTURE_NAME}')
    if meta.get('version') != version:
        fail(f"expected installed version {version}, got {meta.get('version')!r}")
    if meta.get('locked_version') != version:
        fail(f"expected locked version {version}, got {meta.get('locked_version')!r}")
    if meta.get('source_type') != source_type:
        fail(f"expected source_type {source_type!r}, got {meta.get('source_type')!r}")
    manifest_path = meta.get('source_distribution_manifest') or ''
    if f'/{version}/manifest.json' not in manifest_path:
        fail(f'unexpected source_distribution_manifest {manifest_path!r}')
    if meta.get('source_snapshot_tag') != f'skill/{FIXTURE_NAME}/v{version}':
        fail(f"unexpected source_snapshot_tag {meta.get('source_snapshot_tag')!r}")
    content = (target_dir / FIXTURE_NAME / 'VERSION.txt').read_text(encoding='utf-8').strip()
    if content != version:
        fail(f"expected installed VERSION.txt {version!r}, got {content!r}")
    return manifest


def scenario_install_switch_and_rollback_use_distribution_manifests():
    tmpdir, repo = prepare_repo()
    try:
        manifest_v1 = release_current(repo, V1)
        manifest_payload = json.loads(manifest_v1.read_text(encoding='utf-8'))
        dependency_root = (manifest_payload.get('dependencies') or {}).get('root') or {}
        dependency_steps = (manifest_payload.get('dependencies') or {}).get('steps') or []
        if dependency_root.get('name') != FIXTURE_NAME:
            fail(f"expected distribution dependency root {FIXTURE_NAME!r}, got {dependency_root.get('name')!r}")
        if len(dependency_steps) < 1:
            fail('expected distribution manifest to include at least one dependency step')
        attestation_bundle = manifest_payload.get('attestation_bundle') or {}
        if not attestation_bundle.get('provenance_path'):
            fail('expected distribution manifest to include provenance_path')
        if not attestation_bundle.get('signature_path'):
            fail('expected distribution manifest to include signature_path')
        commit_fixture_version(repo, V2)
        release_current(repo, V2)

        shutil.rmtree(repo / 'skills' / 'active' / FIXTURE_NAME)

        target_dir = tmpdir / 'installed'
        target_dir.mkdir(parents=True, exist_ok=True)

        run(
            [str(repo / 'scripts' / 'install-skill.sh'), FIXTURE_NAME, str(target_dir), '--version', V2],
            cwd=repo,
            env=make_env(),
        )
        manifest = assert_current_install(target_dir, V2)
        history = (manifest.get('history') or {}).get(FIXTURE_NAME) or []
        if len(history) != 0:
            fail(f'expected install history length 0 after initial install, got {len(history)}')

        run(
            [str(repo / 'scripts' / 'switch-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--to-version', V1, '--force'],
            cwd=repo,
            env=make_env(),
        )
        manifest = assert_current_install(target_dir, V1)
        history = (manifest.get('history') or {}).get(FIXTURE_NAME) or []
        if len(history) != 1:
            fail(f'expected install history length 1 after switch, got {len(history)}')
        if history[-1].get('version') != V2:
            fail(f"expected latest history entry to preserve {V2}, got {history[-1].get('version')!r}")

        run(
            [str(repo / 'scripts' / 'rollback-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--steps', '1', '--force'],
            cwd=repo,
            env=make_env(),
        )
        manifest = assert_current_install(target_dir, V2)
        history = (manifest.get('history') or {}).get(FIXTURE_NAME) or []
        if len(history) != 2:
            fail(f'expected install history length 2 after rollback, got {len(history)}')

        sync_result = run(
            [str(repo / 'scripts' / 'sync-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(),
        )
        combined = sync_result.stdout + sync_result.stderr
        if 'already up to date' not in combined and 'synced:' not in combined:
            fail(f'unexpected sync output:\n{combined}')
        assert_current_install(target_dir, V2)
    finally:
        shutil.rmtree(tmpdir)


def scenario_manifest_required_ci_blocks_verification_without_ci_sidecar():
    tmpdir, repo = prepare_repo()
    try:
        manifest_path = release_current(repo, V1)
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        attestation_bundle = manifest.get('attestation_bundle') or {}
        attestation_bundle['required_formats'] = ['ci']
        manifest['attestation_bundle'] = attestation_bundle
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        ci_path = repo / 'catalog' / 'provenance' / f'{FIXTURE_NAME}-{V1}.ci.json'
        if ci_path.exists():
            ci_path.unlink()
        result = run(
            [sys.executable, str(repo / 'scripts' / 'verify-distribution-manifest.py'), str(manifest_path)],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'missing CI attestation payload' not in combined:
            fail(f'unexpected CI-required manifest failure:\n{combined}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_installed_distribution_can_be_repaired_after_drift():
    tmpdir, repo = prepare_repo()
    try:
        release_current(repo, V1)
        target_dir = tmpdir / 'installed'
        target_dir.mkdir(parents=True, exist_ok=True)

        run(
            [str(repo / 'scripts' / 'install-skill.sh'), FIXTURE_NAME, str(target_dir), '--version', V1],
            cwd=repo,
            env=make_env(),
        )
        verify_payload = json.loads(
            run(
                [sys.executable, str(repo / 'scripts' / 'verify-installed-skill.py'), FIXTURE_NAME, str(target_dir), '--json'],
                cwd=repo,
                env=make_env(),
            ).stdout
        )
        if verify_payload.get('state') != 'verified':
            fail(f"expected installed distribution to verify cleanly, got {verify_payload.get('state')!r}")

        installed_dir = target_dir / FIXTURE_NAME
        with (installed_dir / 'SKILL.md').open('a', encoding='utf-8') as handle:
            handle.write('\nLocal drift from distribution install.\n')

        drift_payload = json.loads(
            run(
                [sys.executable, str(repo / 'scripts' / 'verify-installed-skill.py'), FIXTURE_NAME, str(target_dir), '--json'],
                cwd=repo,
                env=make_env(),
                expect=1,
            ).stdout
        )
        if drift_payload.get('state') != 'drifted':
            fail(f"expected drifted state after local edit, got {drift_payload.get('state')!r}")

        repair_output = run(
            [str(repo / 'scripts' / 'repair-installed-skill.sh'), FIXTURE_NAME, str(target_dir)],
            cwd=repo,
            env=make_env(),
        ).stdout
        if 'repaired:' not in repair_output:
            fail(f'expected repair output to include repaired:\n{repair_output}')

        verify_payload = json.loads(
            run(
                [sys.executable, str(repo / 'scripts' / 'verify-installed-skill.py'), FIXTURE_NAME, str(target_dir), '--json'],
                cwd=repo,
                env=make_env(),
            ).stdout
        )
        if verify_payload.get('state') != 'verified':
            fail(f"expected repaired distribution install to verify cleanly, got {verify_payload.get('state')!r}")
    finally:
        shutil.rmtree(tmpdir)


def scenario_installed_distribution_verifies_after_legacy_manifest_backfill():
    tmpdir, repo = prepare_repo()
    try:
        manifest_path = release_current(repo, V1)
        legacy_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        legacy_manifest.pop('file_manifest', None)
        legacy_manifest.pop('build', None)
        manifest_path.write_text(json.dumps(legacy_manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        target_dir = tmpdir / 'installed-backfilled'
        target_dir.mkdir(parents=True, exist_ok=True)

        run(
            [str(repo / 'scripts' / 'install-skill.sh'), FIXTURE_NAME, str(target_dir), '--version', V1],
            cwd=repo,
            env=make_env(),
        )

        failed_verify = json.loads(
            run(
                [sys.executable, str(repo / 'scripts' / 'verify-installed-skill.py'), FIXTURE_NAME, str(target_dir), '--json'],
                cwd=repo,
                env=make_env(),
                expect=1,
            ).stdout
        )
        if failed_verify.get('state') != 'failed':
            fail(f"expected explicit verification to fail before backfill, got {failed_verify.get('state')!r}")
        if 'missing signed file_manifest' not in (failed_verify.get('error') or ''):
            fail(f'expected explicit verification to fail on missing signed file_manifest, got {failed_verify!r}')

        backfill_payload = json.loads(
            run(
                [
                    sys.executable,
                    str(repo / 'scripts' / 'backfill-distribution-manifests.py'),
                    '--manifest',
                    str(manifest_path),
                    '--write',
                    '--json',
                ],
                cwd=repo,
                env=make_env(),
            ).stdout
        )
        if backfill_payload.get('state') not in {'backfilled', 'unchanged'}:
            fail(f"expected backfill state 'backfilled' or 'unchanged', got {backfill_payload.get('state')!r}")

        verified_payload = json.loads(
            run(
                [sys.executable, str(repo / 'scripts' / 'verify-installed-skill.py'), FIXTURE_NAME, str(target_dir), '--json'],
                cwd=repo,
                env=make_env(),
            ).stdout
        )
        if verified_payload.get('state') != 'verified':
            fail(f"expected explicit verification success after backfill, got {verified_payload.get('state')!r}")
    finally:
        shutil.rmtree(tmpdir)


def scenario_switch_and_rollback_force_bypass_stale_guardrails_and_keep_drift_precedence():
    tmpdir, repo = prepare_repo()
    try:
        release_current(repo, V1)
        commit_fixture_version(repo, V2)
        release_current(repo, V2)
        shutil.rmtree(repo / 'skills' / 'active' / FIXTURE_NAME)

        target_dir = tmpdir / 'installed-stale-guardrails'
        target_dir.mkdir(parents=True, exist_ok=True)
        run(
            [str(repo / 'scripts' / 'install-skill.sh'), FIXTURE_NAME, str(target_dir), '--version', V2],
            cwd=repo,
            env=make_env(),
        )
        assert_current_install(target_dir, V2)

        write_install_integrity_policy(repo, stale_policy='fail')
        mark_install_stale(target_dir, FIXTURE_NAME)

        run(
            [str(repo / 'scripts' / 'switch-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--to-version', V1, '--force'],
            cwd=repo,
            env=make_env(),
        )
        assert_current_install(target_dir, V1)

        mark_install_stale(target_dir, FIXTURE_NAME)
        run(
            [str(repo / 'scripts' / 'rollback-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--steps', '1', '--force'],
            cwd=repo,
            env=make_env(),
        )
        assert_current_install(target_dir, V2)

        mark_install_stale(target_dir, FIXTURE_NAME)
        run(
            [str(repo / 'scripts' / 'switch-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--to-version', V1, '--force'],
            cwd=repo,
            env=make_env(),
        )
        assert_current_install(target_dir, V1)

        mark_install_stale(target_dir, FIXTURE_NAME)
        installed_dir = target_dir / FIXTURE_NAME
        with (installed_dir / 'SKILL.md').open('a', encoding='utf-8') as handle:
            handle.write('\nLocal drift before switch/rollback precedence checks.\n')

        switch_drift = run(
            [str(repo / 'scripts' / 'switch-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--to-version', V1],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        switch_drift_output = switch_drift.stdout + switch_drift.stderr
        if 'verify-installed-skill.py' not in switch_drift_output or 'repair-installed-skill.sh' not in switch_drift_output:
            fail(f'expected switch drift precedence output to recommend verify+repair\n{switch_drift_output}')
        if 'report-installed-integrity.py' in switch_drift_output:
            fail(f'expected switch drift precedence to avoid stale refresh guidance\n{switch_drift_output}')

        rollback_drift = run(
            [str(repo / 'scripts' / 'rollback-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--steps', '1'],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        rollback_drift_output = rollback_drift.stdout + rollback_drift.stderr
        if 'verify-installed-skill.py' not in rollback_drift_output or 'repair-installed-skill.sh' not in rollback_drift_output:
            fail(f'expected rollback drift precedence output to recommend verify+repair\n{rollback_drift_output}')
        if 'report-installed-integrity.py' in rollback_drift_output:
            fail(f'expected rollback drift precedence to avoid stale refresh guidance\n{rollback_drift_output}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_switch_and_rollback_never_verified_guardrails_and_force_bypass():
    tmpdir, repo = prepare_repo()
    try:
        release_current(repo, V1)
        commit_fixture_version(repo, V2)
        release_current(repo, V2)
        shutil.rmtree(repo / 'skills' / 'active' / FIXTURE_NAME)

        target_dir = tmpdir / 'installed-never-verified-guardrails'
        target_dir.mkdir(parents=True, exist_ok=True)
        run(
            [str(repo / 'scripts' / 'install-skill.sh'), FIXTURE_NAME, str(target_dir), '--version', V2],
            cwd=repo,
            env=make_env(),
        )
        assert_current_install(target_dir, V2)

        write_install_integrity_policy(repo, stale_policy='warn', never_verified_policy='warn')
        mark_install_never_verified(target_dir, FIXTURE_NAME)

        switch_warn = run(
            [str(repo / 'scripts' / 'switch-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--to-version', V1],
            cwd=repo,
            env=make_env(),
        )
        switch_warn_output = switch_warn.stdout + switch_warn.stderr
        if 'report-installed-integrity.py' not in switch_warn_output or '--refresh' not in switch_warn_output:
            fail(f'expected never-verified warn switch output to recommend refresh command\n{switch_warn_output}')
        assert_current_install(target_dir, V1)

        mark_install_never_verified(target_dir, FIXTURE_NAME)
        rollback_warn = run(
            [str(repo / 'scripts' / 'rollback-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--steps', '1'],
            cwd=repo,
            env=make_env(),
        )
        rollback_warn_output = rollback_warn.stdout + rollback_warn.stderr
        if 'report-installed-integrity.py' not in rollback_warn_output or '--refresh' not in rollback_warn_output:
            fail(f'expected never-verified warn rollback output to recommend refresh command\n{rollback_warn_output}')
        assert_current_install(target_dir, V2)

        write_install_integrity_policy(repo, stale_policy='warn', never_verified_policy='fail')
        mark_install_never_verified(target_dir, FIXTURE_NAME)
        switch_fail = run(
            [str(repo / 'scripts' / 'switch-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--to-version', V1],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        switch_fail_output = switch_fail.stdout + switch_fail.stderr
        if 'report-installed-integrity.py' not in switch_fail_output or '--refresh' not in switch_fail_output:
            fail(f'expected never-verified fail switch output to recommend refresh command\n{switch_fail_output}')
        assert_current_install(target_dir, V2)

        mark_install_never_verified(target_dir, FIXTURE_NAME)
        rollback_fail = run(
            [str(repo / 'scripts' / 'rollback-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--steps', '1'],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        rollback_fail_output = rollback_fail.stdout + rollback_fail.stderr
        if 'report-installed-integrity.py' not in rollback_fail_output or '--refresh' not in rollback_fail_output:
            fail(f'expected never-verified fail rollback output to recommend refresh command\n{rollback_fail_output}')
        assert_current_install(target_dir, V2)

        mark_install_never_verified(target_dir, FIXTURE_NAME)
        run(
            [str(repo / 'scripts' / 'switch-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--to-version', V1, '--force'],
            cwd=repo,
            env=make_env(),
        )
        assert_current_install(target_dir, V1)

        mark_install_never_verified(target_dir, FIXTURE_NAME)
        run(
            [str(repo / 'scripts' / 'rollback-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--steps', '1', '--force'],
            cwd=repo,
            env=make_env(),
        )
        assert_current_install(target_dir, V2)

        mark_install_never_verified(target_dir, FIXTURE_NAME)
        installed_dir = target_dir / FIXTURE_NAME
        with (installed_dir / 'SKILL.md').open('a', encoding='utf-8') as handle:
            handle.write('\nLocal drift before never-verified switch/rollback precedence checks.\n')

        switch_drift = run(
            [str(repo / 'scripts' / 'switch-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--to-version', V1],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        switch_drift_output = switch_drift.stdout + switch_drift.stderr
        if 'verify-installed-skill.py' not in switch_drift_output or 'repair-installed-skill.sh' not in switch_drift_output:
            fail(f'expected never-verified switch drift precedence output to recommend verify+repair\n{switch_drift_output}')
        if 'report-installed-integrity.py' in switch_drift_output:
            fail(f'expected never-verified switch drift precedence to avoid refresh guidance\n{switch_drift_output}')

        rollback_drift = run(
            [str(repo / 'scripts' / 'rollback-installed-skill.sh'), FIXTURE_NAME, str(target_dir), '--steps', '1'],
            cwd=repo,
            env=make_env(),
            expect=1,
        )
        rollback_drift_output = rollback_drift.stdout + rollback_drift.stderr
        if 'verify-installed-skill.py' not in rollback_drift_output or 'repair-installed-skill.sh' not in rollback_drift_output:
            fail(f'expected never-verified rollback drift precedence output to recommend verify+repair\n{rollback_drift_output}')
        if 'report-installed-integrity.py' in rollback_drift_output:
            fail(f'expected never-verified rollback drift precedence to avoid refresh guidance\n{rollback_drift_output}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_install_switch_and_rollback_use_distribution_manifests()
    scenario_manifest_required_ci_blocks_verification_without_ci_sidecar()
    scenario_installed_distribution_can_be_repaired_after_drift()
    scenario_installed_distribution_verifies_after_legacy_manifest_backfill()
    scenario_switch_and_rollback_force_bypass_stale_guardrails_and_keep_drift_precedence()
    scenario_switch_and_rollback_never_verified_guardrails_and_force_bypass()
    print('OK: distribution install checks passed')


if __name__ == '__main__':
    main()
