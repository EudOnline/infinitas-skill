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
EXTERNAL_REGISTRY_NAME = 'external-demo'
EXTERNAL_SKILL_NAME = 'external-only-skill'
EXTERNAL_SKILL_VERSION = '0.9.0'


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
    path.parent.mkdir(parents=True, exist_ok=True)
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
            'summary': f'Fixture skill version {version} for explain-install tests',
            'owner': 'release-test',
            'owners': ['release-test'],
            'author': 'release-test',
            'review_state': 'approved',
            'distribution': {
                'installable': True,
                'channel': 'git',
            },
        }
    )
    write_json(fixture_dir / '_meta.json', meta)
    (fixture_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {FIXTURE_NAME}\n'
        'description: Fixture skill for explain-install tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        f'Current fixture version: {version}.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'VERSION.txt').write_text(version + '\n', encoding='utf-8')
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {version} - 2026-03-14\n'
        f'- Prepared explain-install fixture for {version}.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-14T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for explain-install tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-14T00:05:00Z',
                    'note': 'Fixture approval',
                }
            ],
        },
    )


def external_ai_index_payload():
    return {
        'schema_version': 1,
        'generated_at': '2026-03-14T00:00:00Z',
        'registry': {'default_registry': EXTERNAL_REGISTRY_NAME},
        'install_policy': {
            'mode': 'immutable-only',
            'direct_source_install_allowed': False,
            'require_attestation': True,
            'require_sha256': True,
        },
        'skills': [
            {
                'name': EXTERNAL_SKILL_NAME,
                'publisher': 'partner',
                'qualified_name': f'partner/{EXTERNAL_SKILL_NAME}',
                'summary': 'External fixture skill for explain-install tests',
                'use_when': ['Need external registry coverage'],
                'avoid_when': [],
                'agent_compatible': ['openclaw', 'claude-code', 'codex'],
                'default_install_version': EXTERNAL_SKILL_VERSION,
                'latest_version': EXTERNAL_SKILL_VERSION,
                'available_versions': [EXTERNAL_SKILL_VERSION],
                'entrypoints': {
                    'skill_md': f'skills/active/{EXTERNAL_SKILL_NAME}/SKILL.md',
                },
                'requires': {'tools': [], 'env': []},
                'versions': {
                    EXTERNAL_SKILL_VERSION: {
                        'manifest_path': f'catalog/distributions/_legacy/{EXTERNAL_SKILL_NAME}/{EXTERNAL_SKILL_VERSION}/manifest.json',
                        'distribution_manifest_path': f'catalog/distributions/_legacy/{EXTERNAL_SKILL_NAME}/{EXTERNAL_SKILL_VERSION}/manifest.json',
                        'bundle_path': f'catalog/distributions/_legacy/{EXTERNAL_SKILL_NAME}/{EXTERNAL_SKILL_VERSION}/bundle.tar.gz',
                        'bundle_sha256': 'deadbeef',
                        'attestation_path': f'catalog/provenance/{EXTERNAL_SKILL_NAME}-{EXTERNAL_SKILL_VERSION}.json',
                        'attestation_signature_path': None,
                        'published_at': '2026-03-14T00:00:00Z',
                        'stability': 'stable',
                        'installable': True,
                        'attestation_formats': ['ssh'],
                        'trust_state': 'attested',
                        'resolution': {
                            'preferred_source': 'distribution-manifest',
                            'fallback_allowed': False,
                        },
                    }
                },
            }
        ],
    }


def configure_external_registry(repo: Path, tmpdir: Path):
    external_repo = tmpdir / EXTERNAL_REGISTRY_NAME
    write_json(external_repo / 'catalog' / 'ai-index.json', external_ai_index_payload())
    (external_repo / 'catalog' / 'distributions' / '_legacy' / EXTERNAL_SKILL_NAME / EXTERNAL_SKILL_VERSION).mkdir(parents=True, exist_ok=True)
    (external_repo / 'catalog' / 'provenance').mkdir(parents=True, exist_ok=True)
    (external_repo / 'catalog' / 'distributions' / '_legacy' / EXTERNAL_SKILL_NAME / EXTERNAL_SKILL_VERSION / 'manifest.json').write_text('{}\n', encoding='utf-8')
    (external_repo / 'catalog' / 'distributions' / '_legacy' / EXTERNAL_SKILL_NAME / EXTERNAL_SKILL_VERSION / 'bundle.tar.gz').write_text('fixture\n', encoding='utf-8')
    (external_repo / 'catalog' / 'provenance' / f'{EXTERNAL_SKILL_NAME}-{EXTERNAL_SKILL_VERSION}.json').write_text('{}\n', encoding='utf-8')

    registry_path = repo / 'config' / 'registry-sources.json'
    payload = json.loads(registry_path.read_text(encoding='utf-8'))
    payload['registries'].append(
        {
            'name': EXTERNAL_REGISTRY_NAME,
            'kind': 'local',
            'local_path': os.path.relpath(external_repo, repo),
            'priority': 50,
            'enabled': True,
            'trust': 'trusted',
            'update_policy': {'mode': 'local-only'},
            'notes': 'External fixture registry for explain-install tests',
        }
    )
    write_json(registry_path, payload)
    run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-explain-install-test-'))
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
    run(
        [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
        cwd=repo,
        env=make_env(),
    )
    return tmpdir, repo


def commit_fixture_version(repo: Path, version: str):
    update_fixture(repo, version)
    run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
    run(['git', 'add', 'skills/active/' + FIXTURE_NAME, 'catalog'], cwd=repo)
    run(['git', 'commit', '-m', f'fixture {version}'], cwd=repo)
    run(['git', 'push'], cwd=repo)


def release_current(repo: Path):
    run(
        [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
        cwd=repo,
        env=make_env(),
    )


def assert_explanation(payload, *, registry_name, requires_confirmation, expected_version):
    explanation = payload.get('explanation')
    if not isinstance(explanation, dict):
        fail(f'expected explanation object, got {explanation!r}')
    if not isinstance(explanation.get('selection_reason'), str) or not explanation.get('selection_reason').strip():
        fail(f"expected selection_reason, got {explanation.get('selection_reason')!r}")
    if explanation.get('registry_used') != registry_name:
        fail(f"expected registry_used {registry_name!r}, got {explanation.get('registry_used')!r}")
    if explanation.get('confirmation_required') is not requires_confirmation:
        fail(
            f"expected confirmation_required {requires_confirmation!r}, "
            f"got {explanation.get('confirmation_required')!r}"
        )
    if not isinstance(explanation.get('version_reason'), str) or expected_version not in explanation.get('version_reason'):
        fail(f"expected version_reason to mention {expected_version!r}, got {explanation.get('version_reason')!r}")
    if not isinstance(explanation.get('next_actions'), list) or not explanation.get('next_actions'):
        fail(f"expected next_actions list, got {explanation.get('next_actions')!r}")


def main():
    tmpdir, repo = prepare_repo()
    try:
        private_payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), FIXTURE_NAME], cwd=repo).stdout)
        assert_explanation(private_payload, registry_name='self', requires_confirmation=False, expected_version=V1)

        target_dir = tmpdir / 'installed'
        run([str(repo / 'scripts' / 'install-by-name.sh'), FIXTURE_NAME, str(target_dir), '--version', V1], cwd=repo)

        commit_fixture_version(repo, V2)
        release_current(repo)
        shutil.rmtree(repo / 'skills' / 'active' / FIXTURE_NAME)

        update_payload = json.loads(run([str(repo / 'scripts' / 'check-skill-update.sh'), FIXTURE_NAME, str(target_dir)], cwd=repo).stdout)
        assert_explanation(update_payload, registry_name='self', requires_confirmation=False, expected_version=V2)
        if V1 not in ((update_payload.get('explanation') or {}).get('version_reason') or ''):
            fail('expected update explanation to mention installed version')

        plan_payload = json.loads(
            run([str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir), '--mode', 'confirm'], cwd=repo).stdout
        )
        assert_explanation(plan_payload, registry_name='self', requires_confirmation=False, expected_version=V2)
        plan_policy_reasons = ((plan_payload.get('explanation') or {}).get('policy_reasons') or [])
        if not plan_policy_reasons:
            fail('expected policy_reasons in confirm upgrade plan')

        configure_external_registry(repo, tmpdir)
        external_payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), EXTERNAL_SKILL_NAME], cwd=repo).stdout)
        assert_explanation(
            external_payload,
            registry_name=EXTERNAL_REGISTRY_NAME,
            requires_confirmation=True,
            expected_version=EXTERNAL_SKILL_VERSION,
        )
        policy_reasons = ((external_payload.get('explanation') or {}).get('policy_reasons') or [])
        if not policy_reasons:
            fail('expected policy_reasons for external resolution')

        blocked = run(
            [str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir), '--registry', 'other-registry'],
            cwd=repo,
            expect=1,
        )
        blocked_payload = json.loads(blocked.stdout)
        blocked_reasons = ((blocked_payload.get('explanation') or {}).get('policy_reasons') or [])
        if not any('cross-source' in reason for reason in blocked_reasons):
            fail(f'expected cross-source policy reason, got {blocked_reasons!r}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: explain install checks passed')


if __name__ == '__main__':
    main()
