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
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.testing.env import build_regression_test_env

FIXTURE_NAME = 'release-fixture'
V1 = '1.2.3'
V2 = '1.2.4'
EXTERNAL_REGISTRY_NAME = 'external-demo'
EXTERNAL_SKILL_NAME = 'external-only-skill'
EXTERNAL_SKILL_VERSION = '0.9.0'
PLATFORM_EVIDENCE_MINUTES = {
    'codex': 0,
    'claude': 1,
    'openclaw': 2,
}
OPENCLAW_RUNTIME = {
    'platform': 'openclaw',
    'source_mode': 'legacy',
    'workspace_scope': 'workspace',
    'workspace_targets': ['skills', '.agents/skills', '~/.agents/skills', '~/.openclaw/skills'],
    'skill_precedence': ['skills', '.agents/skills', '~/.agents/skills', '~/.openclaw/skills', 'bundled', 'extra'],
    'install_targets': {
        'workspace': ['skills', '.agents/skills'],
        'shared': ['~/.agents/skills', '~/.openclaw/skills'],
    },
    'requires': {'tools': [], 'bins': [], 'env': [], 'config': []},
    'plugin_capabilities': {},
    'background_tasks': {'required': False},
    'subagents': {'required': False},
    'legacy_compatibility': {'agent_compatible': ['openclaw', 'claude-code', 'codex'], 'agent_compatible_deprecated': True},
    'readiness': {
        'ready': True,
        'supports_background_tasks': True,
        'supports_plugins': True,
        'supports_subagents': True,
        'status': 'ready',
    },
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def contract_checked_at(repo: Path, platform: str):
    profile_path = repo / 'profiles' / f'{platform}.json'
    payload = json.loads(profile_path.read_text(encoding='utf-8'))
    contract = payload.get('contract') if isinstance(payload.get('contract'), dict) else {}
    last_verified = contract.get('last_verified')
    if not isinstance(last_verified, str) or not last_verified:
        fail(f'missing contract.last_verified for platform {platform!r}')
    minute = PLATFORM_EVIDENCE_MINUTES.get(platform, 0)
    return f'{last_verified}T12:{minute:02d}:00Z'


def iso_hours_ago(hours: int):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def make_env(extra=None):
    return build_regression_test_env(ROOT, extra=extra, env=os.environ.copy())


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
            'maintainers': ['Release Fixture'],
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
    sync_platform_evidence(repo, version)


def sync_platform_evidence(repo: Path, version: str):
    for platform in ('codex', 'claude', 'openclaw'):
        path = repo / 'catalog' / 'compatibility-evidence' / platform / FIXTURE_NAME / f'{version}.json'
        write_json(
            path,
            {
                'platform': platform,
                'skill': FIXTURE_NAME,
                'version': version,
                'state': 'adapted',
                'checked_at': contract_checked_at(repo, platform),
                'checker': f'check-{platform}-compat.py',
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
                'tags': ['external', 'fixture'],
                'use_when': ['Need external registry coverage'],
                'avoid_when': [],
                'runtime_assumptions': ['A trusted external registry is configured'],
                'agent_compatible': ['openclaw', 'claude-code', 'codex'],
                'maturity': 'stable',
                'quality_score': 66,
                'last_verified_at': '2026-03-14T00:00:00Z',
                'capabilities': ['external-coverage', 'install-explanation'],
                'verified_support': {},
                'trust_state': 'attested',
                'runtime': OPENCLAW_RUNTIME,
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


def assert_mutation_fields(payload, *, readiness, policy, reason_code, recovery_action):
    if payload.get('mutation_readiness') != readiness:
        fail(f"expected mutation_readiness {readiness!r}, got {payload!r}")
    if payload.get('mutation_policy') != policy:
        fail(f"expected mutation_policy {policy!r}, got {payload!r}")
    if payload.get('mutation_reason_code') != reason_code:
        fail(f"expected mutation_reason_code {reason_code!r}, got {payload!r}")
    if payload.get('recovery_action') != recovery_action:
        fail(f"expected recovery_action {recovery_action!r}, got {payload!r}")


def main():
    tmpdir, repo = prepare_repo()
    try:
        private_payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), FIXTURE_NAME], cwd=repo).stdout)
        assert_explanation(private_payload, registry_name='self', requires_confirmation=False, expected_version=V1)

        target_dir = tmpdir / 'installed'
        run([str(repo / 'scripts' / 'install-by-name.sh'), FIXTURE_NAME, str(target_dir), '--version', V1], cwd=repo)

        no_upgrade_plan_payload = json.loads(
            run([str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir), '--mode', 'confirm'], cwd=repo).stdout
        )
        if no_upgrade_plan_payload.get('state') != 'up-to-date':
            fail(f"expected confirm no-op state 'up-to-date', got {no_upgrade_plan_payload!r}")
        if no_upgrade_plan_payload.get('to_version') != V1:
            fail(f"expected confirm no-op to_version {V1!r}, got {no_upgrade_plan_payload!r}")
        if no_upgrade_plan_payload.get('next_step') != 'use-installed-skill':
            fail(f"expected confirm no-op next_step 'use-installed-skill', got {no_upgrade_plan_payload!r}")
        assert_mutation_fields(no_upgrade_plan_payload, readiness='ready', policy=None, reason_code=None, recovery_action='none')

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
        assert_mutation_fields(plan_payload, readiness='ready', policy=None, reason_code=None, recovery_action='none')
        plan_policy_reasons = ((plan_payload.get('explanation') or {}).get('policy_reasons') or [])
        if not plan_policy_reasons:
            fail('expected policy_reasons in confirm upgrade plan')

        write_install_integrity_policy(repo, stale_policy='fail')
        mark_install_stale(target_dir, FIXTURE_NAME)
        stale_no_upgrade_payload = json.loads(
            run(
                [
                    str(repo / 'scripts' / 'upgrade-skill.sh'),
                    FIXTURE_NAME,
                    str(target_dir),
                    '--mode',
                    'confirm',
                    '--to-version',
                    V1,
                ],
                cwd=repo,
            ).stdout
        )
        if stale_no_upgrade_payload.get('state') != 'up-to-date':
            fail(f"expected stale confirm no-op state 'up-to-date', got {stale_no_upgrade_payload!r}")
        if stale_no_upgrade_payload.get('freshness_state') != 'stale':
            fail(f"expected stale confirm no-op freshness_state 'stale', got {stale_no_upgrade_payload!r}")
        assert_mutation_fields(
            stale_no_upgrade_payload,
            readiness='blocked',
            policy='fail',
            reason_code='stale-installed-integrity',
            recovery_action='refresh',
        )

        write_install_integrity_policy(repo, stale_policy='warn', never_verified_policy='fail')
        mark_install_never_verified(target_dir, FIXTURE_NAME)
        never_verified_no_upgrade_payload = json.loads(
            run(
                [
                    str(repo / 'scripts' / 'upgrade-skill.sh'),
                    FIXTURE_NAME,
                    str(target_dir),
                    '--mode',
                    'confirm',
                    '--to-version',
                    V1,
                ],
                cwd=repo,
            ).stdout
        )
        if never_verified_no_upgrade_payload.get('state') != 'up-to-date':
            fail(
                "expected never-verified confirm no-op state 'up-to-date', "
                f"got {never_verified_no_upgrade_payload!r}"
            )
        if never_verified_no_upgrade_payload.get('freshness_state') != 'never-verified':
            fail(
                "expected never-verified confirm no-op freshness_state 'never-verified', "
                f"got {never_verified_no_upgrade_payload!r}"
            )
        assert_mutation_fields(
            never_verified_no_upgrade_payload,
            readiness='blocked',
            policy='fail',
            reason_code='never-verified-installed-integrity',
            recovery_action='refresh',
        )

        write_install_integrity_policy(repo, stale_policy='warn', never_verified_policy='warn')
        mark_install_never_verified(target_dir, FIXTURE_NAME)
        never_verified_update_payload = json.loads(
            run([str(repo / 'scripts' / 'check-skill-update.sh'), FIXTURE_NAME, str(target_dir)], cwd=repo).stdout
        )
        assert_explanation(never_verified_update_payload, registry_name='self', requires_confirmation=False, expected_version=V2)
        never_verified_update_reasons = ((never_verified_update_payload.get('explanation') or {}).get('policy_reasons') or [])
        if not any('never-verified' in reason.lower() for reason in never_verified_update_reasons):
            fail(f'expected never-verified policy reason in update explanation, got {never_verified_update_reasons!r}')
        never_verified_update_actions = ((never_verified_update_payload.get('explanation') or {}).get('next_actions') or [])
        if not any('report-installed-integrity.py' in action and '--refresh' in action for action in never_verified_update_actions):
            fail(
                'expected never-verified update next_actions to recommend refresh, '
                f'got {never_verified_update_actions!r}'
            )

        never_verified_plan_payload = json.loads(
            run([str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir), '--mode', 'confirm'], cwd=repo).stdout
        )
        assert_explanation(never_verified_plan_payload, registry_name='self', requires_confirmation=False, expected_version=V2)
        assert_mutation_fields(
            never_verified_plan_payload,
            readiness='warning',
            policy='warn',
            reason_code='never-verified-installed-integrity',
            recovery_action='refresh',
        )
        never_verified_plan_reasons = ((never_verified_plan_payload.get('explanation') or {}).get('policy_reasons') or [])
        if not any('never-verified' in reason.lower() for reason in never_verified_plan_reasons):
            fail(f'expected never-verified policy reason in confirm explanation, got {never_verified_plan_reasons!r}')
        never_verified_plan_actions = ((never_verified_plan_payload.get('explanation') or {}).get('next_actions') or [])
        if not any('report-installed-integrity.py' in action and '--refresh' in action for action in never_verified_plan_actions):
            fail(
                'expected never-verified confirm next_actions to recommend refresh, '
                f'got {never_verified_plan_actions!r}'
            )

        write_install_integrity_policy(repo, stale_policy='warn')
        mark_install_stale(target_dir, FIXTURE_NAME)
        stale_warn_payload = json.loads(
            run([str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir), '--mode', 'confirm'], cwd=repo).stdout
        )
        assert_mutation_fields(
            stale_warn_payload,
            readiness='warning',
            policy='warn',
            reason_code='stale-installed-integrity',
            recovery_action='refresh',
        )
        stale_warn_reasons = ((stale_warn_payload.get('explanation') or {}).get('policy_reasons') or [])
        if not any('stale' in reason.lower() for reason in stale_warn_reasons):
            fail(f'expected stale warning policy reason, got {stale_warn_reasons!r}')
        stale_warn_actions = ((stale_warn_payload.get('explanation') or {}).get('next_actions') or [])
        if not any('report-installed-integrity.py' in action for action in stale_warn_actions):
            fail(f'expected stale warning next_actions to recommend refresh, got {stale_warn_actions!r}')

        write_install_integrity_policy(repo, stale_policy='fail')
        blocked = run(
            [str(repo / 'scripts' / 'upgrade-skill.sh'), FIXTURE_NAME, str(target_dir), '--mode', 'confirm'],
            cwd=repo,
            expect=1,
        )
        blocked_payload = json.loads(blocked.stdout)
        if blocked_payload.get('error_code') != 'stale-installed-integrity':
            fail(f"expected stale-installed-integrity error_code, got {blocked_payload!r}")
        assert_mutation_fields(
            blocked_payload,
            readiness='blocked',
            policy='fail',
            reason_code='stale-installed-integrity',
            recovery_action='refresh',
        )
        blocked_actions = ((blocked_payload.get('explanation') or {}).get('next_actions') or [])
        if not any('report-installed-integrity.py' in action for action in blocked_actions):
            fail(f'expected stale block next_actions to recommend refresh, got {blocked_actions!r}')

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
