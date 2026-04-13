#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from result_schema_lib import validate_pull_result

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers.env import make_test_env
from tests.helpers.repo_copy import copy_repo_without_local_state
from tests.helpers.signing import add_allowed_signer, configure_git_ssh_signing, generate_signing_key

FIXTURE_NAME = 'release-fixture'
FIXTURE_VERSION = '1.2.3'
EXTERNAL_REGISTRY_NAME = 'external-demo'
EXTERNAL_SKILL_NAME = 'demo-skill'
EXTERNAL_SKILL_VERSION = '1.2.3'
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


def scaffold_fixture(repo: Path):
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
            'summary': 'Fixture skill for ai pull tests',
            'owner': 'release-test',
            'owners': ['release-test'],
            'maintainers': ['Release Fixture'],
            'author': 'release-test',
            'review_state': 'approved',
        }
    )
    write_json(fixture_dir / '_meta.json', meta)
    (fixture_dir / 'SKILL.md').write_text(
        '---\n'
        f'name: {FIXTURE_NAME}\n'
        'description: Fixture skill for ai pull tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated AI pull tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-09\n'
        '- Added AI pull fixture release.\n',
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
                    'note': 'Fixture approval for AI pull tests',
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
    sync_platform_evidence(repo)


def sync_platform_evidence(repo: Path):
    for platform in ('codex', 'claude', 'openclaw'):
        path = repo / 'catalog' / 'compatibility-evidence' / platform / FIXTURE_NAME / f'{FIXTURE_VERSION}.json'
        write_json(
            path,
            {
                'platform': platform,
                'skill': FIXTURE_NAME,
                'version': FIXTURE_VERSION,
                'state': 'adapted',
                'checked_at': contract_checked_at(repo, platform),
                'checker': f'check-{platform}-compat.py',
            },
        )


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-ai-pull-test-'))
    repo = copy_repo_without_local_state(tmpdir)
    origin = tmpdir / 'origin.git'
    scaffold_fixture(repo)
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

    key_path = generate_signing_key(tmpdir, identity='release-test')
    add_allowed_signer(repo / 'config' / 'allowed_signers', identity='release-test', key_path=key_path)
    configure_git_ssh_signing(repo, key_path)
    run(['git', 'add', 'config/allowed_signers'], cwd=repo)
    run(['git', 'commit', '-m', 'add release signer'], cwd=repo)
    run(['git', 'push'], cwd=repo)
    run(
        [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
        cwd=repo,
        env=make_test_env(),
    )
    return tmpdir, repo


def external_ai_index_payload():
    return {
        'schema_version': 1,
        'generated_at': '2026-03-12T00:00:00Z',
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
                'summary': 'External fixture skill for registry-aware pull tests',
                'tags': ['external', 'fixture'],
                'use_when': ['Need external registry coverage'],
                'avoid_when': [],
                'runtime_assumptions': ['A trusted external registry is configured'],
                'agent_compatible': ['openclaw', 'claude-code', 'codex'],
                'maturity': 'stable',
                'quality_score': 65,
                'last_verified_at': '2026-03-12T00:00:00Z',
                'capabilities': ['external-coverage', 'pull'],
                'verified_support': {},
                'trust_state': 'attested',
                'default_install_version': EXTERNAL_SKILL_VERSION,
                'latest_version': EXTERNAL_SKILL_VERSION,
                'available_versions': [EXTERNAL_SKILL_VERSION],
                'entrypoints': {
                    'skill_md': f'skills/active/{EXTERNAL_SKILL_NAME}/SKILL.md',
                },
                'requires': {'tools': [], 'env': []},
                'interop': {
                    'openclaw': {
                        'runtime_targets': ['~/.openclaw/skills', '~/.openclaw/workspace/skills'],
                        'import_supported': True,
                        'export_supported': True,
                        'public_publish': {
                            'clawhub': {
                                'supported': True,
                                'default': False,
                            }
                        },
                    }
                },
                'runtime': OPENCLAW_RUNTIME,
                'versions': {
                    EXTERNAL_SKILL_VERSION: {
                        'manifest_path': f'catalog/distributions/_legacy/{EXTERNAL_SKILL_NAME}/{EXTERNAL_SKILL_VERSION}/manifest.json',
                        'distribution_manifest_path': f'catalog/distributions/_legacy/{EXTERNAL_SKILL_NAME}/{EXTERNAL_SKILL_VERSION}/manifest.json',
                        'bundle_path': f'catalog/distributions/_legacy/{EXTERNAL_SKILL_NAME}/{EXTERNAL_SKILL_VERSION}/bundle.tar.gz',
                        'bundle_sha256': 'deadbeef',
                        'attestation_path': f'catalog/provenance/{EXTERNAL_SKILL_NAME}-{EXTERNAL_SKILL_VERSION}.json',
                        'attestation_signature_path': None,
                        'published_at': '2026-03-12T00:00:00Z',
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
            'notes': 'External fixture registry for ai pull tests',
        }
    )
    write_json(registry_path, payload)


def main():
    tmpdir, repo = prepare_repo()
    try:
        configure_external_registry(repo, tmpdir)
        external_repo = tmpdir / EXTERNAL_REGISTRY_NAME
        target = tmpdir / 'installed'
        result = run([str(repo / 'scripts' / 'pull-skill.sh'), FIXTURE_NAME, str(target)], cwd=repo)
        payload = json.loads(result.stdout)
        errors = validate_pull_result(payload)
        if errors:
            fail('pull success result schema errors:\n' + '\n'.join(errors))
        if payload.get('ok') is not True:
            fail(f'expected pull ok=true, got {payload!r}')
        if payload.get('state') != 'installed':
            fail(f"expected installed state, got {payload.get('state')!r}")
        if payload.get('resolved_version') != FIXTURE_VERSION:
            fail(f"expected resolved version {FIXTURE_VERSION!r}, got {payload.get('resolved_version')!r}")
        lockfile = Path(payload.get('lockfile_path') or '')
        if not lockfile.exists():
            fail(f'missing lockfile {lockfile}')
        installed_skill = target / FIXTURE_NAME
        if not installed_skill.is_dir():
            fail(f'missing installed skill directory {installed_skill}')

        missing_version = run([str(repo / 'scripts' / 'pull-skill.sh'), FIXTURE_NAME, str(target), '--version', '9.9.9'], cwd=repo, expect=1)
        missing_version_payload = json.loads(missing_version.stdout)
        errors = validate_pull_result(missing_version_payload)
        if errors:
            fail('pull version-not-found result schema errors:\n' + '\n'.join(errors))

        confirm_target = tmpdir / 'confirm-target'
        result = run([str(repo / 'scripts' / 'pull-skill.sh'), FIXTURE_NAME, str(confirm_target), '--mode', 'confirm'], cwd=repo)
        confirm_payload = json.loads(result.stdout)
        errors = validate_pull_result(confirm_payload)
        if errors:
            fail('pull confirm result schema errors:\n' + '\n'.join(errors))
        if confirm_payload.get('state') != 'planned':
            fail(f"expected planned state for confirm mode, got {confirm_payload.get('state')!r}")
        if confirm_target.exists():
            fail('confirm mode unexpectedly created target directory')

        external_target = tmpdir / 'external-confirm-target'
        result = run(
            [
                str(repo / 'scripts' / 'pull-skill.sh'),
                f'partner/{EXTERNAL_SKILL_NAME}',
                str(external_target),
                '--registry',
                EXTERNAL_REGISTRY_NAME,
                '--mode',
                'confirm',
            ],
            cwd=repo,
        )
        external_payload = json.loads(result.stdout)
        errors = validate_pull_result(external_payload)
        if errors:
            fail('pull external confirm result schema errors:\n' + '\n'.join(errors))
        if external_payload.get('qualified_name') != f'partner/{EXTERNAL_SKILL_NAME}':
            fail(f"expected external qualified_name partner/{EXTERNAL_SKILL_NAME!s}, got {external_payload.get('qualified_name')!r}")
        if external_payload.get('registry_name') != EXTERNAL_REGISTRY_NAME:
            fail(f"expected registry_name {EXTERNAL_REGISTRY_NAME!r}, got {external_payload.get('registry_name')!r}")
        if external_payload.get('resolved_version') != EXTERNAL_SKILL_VERSION:
            fail(f"expected resolved version {EXTERNAL_SKILL_VERSION!r}, got {external_payload.get('resolved_version')!r}")
        if external_payload.get('state') != 'planned':
            fail(f"expected planned state for external confirm mode, got {external_payload.get('state')!r}")

        bad_version = run(
            [
                str(repo / 'scripts' / 'pull-skill.sh'),
                f'partner/{EXTERNAL_SKILL_NAME}',
                str(external_target),
                '--registry',
                EXTERNAL_REGISTRY_NAME,
                '--version',
                '9.9.9',
            ],
            cwd=repo,
            expect=1,
        )
        combined = bad_version.stdout + bad_version.stderr
        bad_version_payload = json.loads(bad_version.stdout)
        errors = validate_pull_result(bad_version_payload)
        if errors:
            fail('pull external bad-version result schema errors:\n' + '\n'.join(errors))
        if 'version-not-found' not in combined:
            fail(f'expected version-not-found in external registry failure\n{combined}')

        manifest_path = external_repo / 'catalog' / 'distributions' / '_legacy' / EXTERNAL_SKILL_NAME / EXTERNAL_SKILL_VERSION / 'manifest.json'
        bundle_path = external_repo / 'catalog' / 'distributions' / '_legacy' / EXTERNAL_SKILL_NAME / EXTERNAL_SKILL_VERSION / 'bundle.tar.gz'
        attestation_path = external_repo / 'catalog' / 'provenance' / f'{EXTERNAL_SKILL_NAME}-{EXTERNAL_SKILL_VERSION}.json'

        manifest_backup = manifest_path.read_text(encoding='utf-8')
        manifest_path.unlink()
        missing_manifest = run(
            [
                str(repo / 'scripts' / 'pull-skill.sh'),
                f'partner/{EXTERNAL_SKILL_NAME}',
                str(external_target),
                '--registry',
                EXTERNAL_REGISTRY_NAME,
            ],
            cwd=repo,
            expect=1,
        )
        missing_manifest_payload = json.loads(missing_manifest.stdout)
        errors = validate_pull_result(missing_manifest_payload)
        if errors:
            fail('pull missing-manifest result schema errors:\n' + '\n'.join(errors))
        if missing_manifest_payload.get('error_code') != 'missing-distribution-file':
            fail(f"expected missing-distribution-file for missing manifest, got {missing_manifest_payload!r}")
        if 'manifest_path' not in (missing_manifest_payload.get('message') or ''):
            fail(f'expected missing manifest message to mention manifest_path, got {missing_manifest_payload!r}')
        explanation = missing_manifest_payload.get('explanation') or {}
        if not explanation.get('policy_reasons'):
            fail(f'expected explanation on missing manifest failure, got {missing_manifest_payload!r}')
        manifest_path.write_text(manifest_backup, encoding='utf-8')

        bundle_backup = bundle_path.read_text(encoding='utf-8')
        bundle_path.unlink()
        missing_bundle = run(
            [
                str(repo / 'scripts' / 'pull-skill.sh'),
                f'partner/{EXTERNAL_SKILL_NAME}',
                str(external_target),
                '--registry',
                EXTERNAL_REGISTRY_NAME,
            ],
            cwd=repo,
            expect=1,
        )
        missing_bundle_payload = json.loads(missing_bundle.stdout)
        errors = validate_pull_result(missing_bundle_payload)
        if errors:
            fail('pull missing-bundle result schema errors:\n' + '\n'.join(errors))
        if missing_bundle_payload.get('error_code') != 'missing-distribution-file':
            fail(f"expected missing-distribution-file for missing bundle, got {missing_bundle_payload!r}")
        if 'bundle_path' not in (missing_bundle_payload.get('message') or ''):
            fail(f'expected missing bundle message to mention bundle_path, got {missing_bundle_payload!r}')
        explanation = missing_bundle_payload.get('explanation') or {}
        if not explanation.get('next_actions'):
            fail(f'expected explanation on missing bundle failure, got {missing_bundle_payload!r}')
        bundle_path.write_text(bundle_backup, encoding='utf-8')

        attestation_backup = attestation_path.read_text(encoding='utf-8')
        attestation_path.unlink()
        missing_attestation = run(
            [
                str(repo / 'scripts' / 'pull-skill.sh'),
                f'partner/{EXTERNAL_SKILL_NAME}',
                str(external_target),
                '--registry',
                EXTERNAL_REGISTRY_NAME,
            ],
            cwd=repo,
            expect=1,
        )
        missing_attestation_payload = json.loads(missing_attestation.stdout)
        errors = validate_pull_result(missing_attestation_payload)
        if errors:
            fail('pull missing-attestation result schema errors:\n' + '\n'.join(errors))
        if missing_attestation_payload.get('error_code') != 'missing-distribution-file':
            fail(f"expected missing-distribution-file for missing attestation, got {missing_attestation_payload!r}")
        if 'attestation_path' not in (missing_attestation_payload.get('message') or ''):
            fail(f'expected missing attestation message to mention attestation_path, got {missing_attestation_payload!r}')
        explanation = missing_attestation_payload.get('explanation') or {}
        if not explanation.get('selection_reason'):
            fail(f'expected explanation on missing attestation failure, got {missing_attestation_payload!r}')
        attestation_path.write_text(attestation_backup, encoding='utf-8')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: ai pull checks passed')


if __name__ == '__main__':
    main()
