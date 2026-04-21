#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from infinitas_skill.testing.env import build_regression_test_env

FIXTURE_NAME = 'release-fixture'
FIXTURE_VERSION = '1.2.3'
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


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def make_env(extra=None):
    return build_regression_test_env(ROOT, extra=extra, env=os.environ.copy())


def cli_env(repo: Path):
    env = dict(os.environ, PYTHONPATH=str(repo / 'src'))
    return build_regression_test_env(ROOT, extra=env, env=os.environ.copy())


def cli_command(*args: str):
    return [sys.executable, '-m', 'infinitas_skill.cli.main', *args]


def run_cli(repo: Path, args: list[str], expect=0):
    return run(cli_command(*args), cwd=repo, expect=expect, env=cli_env(repo))


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
            'summary': 'Fixture skill for install-by-name tests',
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
        'description: Fixture skill for install-by-name tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated install-by-name tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-12\n'
        '- Added install-by-name fixture release.\n',
        encoding='utf-8',
    )
    write_json(
        fixture_dir / 'reviews.json',
        {
            'version': 1,
            'requests': [
                {
                    'requested_at': '2026-03-12T00:00:00Z',
                    'requested_by': 'release-test',
                    'note': 'Fixture approval for install-by-name tests',
                }
            ],
            'entries': [
                {
                    'reviewer': 'lvxiaoer',
                    'decision': 'approved',
                    'at': '2026-03-12T00:05:00Z',
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
                'summary': 'External fixture skill for install-by-name tests',
                'tags': ['external', 'fixture'],
                'use_when': ['Need external registry coverage'],
                'avoid_when': [],
                'runtime_assumptions': ['A trusted external registry is configured'],
                'agent_compatible': ['openclaw', 'claude-code', 'codex'],
                'maturity': 'stable',
                'quality_score': 64,
                'last_verified_at': '2026-03-12T00:00:00Z',
                'capabilities': ['external-coverage', 'install'],
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
            'notes': 'External fixture registry for install-by-name tests',
        }
    )
    write_json(registry_path, payload)
    run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)


def add_discovery_fixture(repo: Path, entry):
    index_path = repo / 'catalog' / 'discovery-index.json'
    payload = load_json(index_path)
    payload.setdefault('skills', []).append(entry)
    write_json(index_path, payload)


def read_install_manifest(target_dir: Path):
    manifest = target_dir / '.infinitas-skill-install-manifest.json'
    if not manifest.exists():
        fail(f'missing install manifest: {manifest}')
    return json.loads(manifest.read_text(encoding='utf-8'))


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-install-by-name-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
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
    configure_external_registry(repo, tmpdir)
    return tmpdir, repo


def main():
    tmpdir, repo = prepare_repo()
    try:
        target_dir = tmpdir / 'installed'
        run_cli(repo, ['install', 'by-name', FIXTURE_NAME, str(target_dir), '--json'])
        manifest = read_install_manifest(target_dir)
        entry = (manifest.get('skills') or {}).get(FIXTURE_NAME) or {}
        if entry.get('source_registry') != 'self':
            fail(f"expected source_registry self, got {entry.get('source_registry')!r}")
        if entry.get('qualified_name') != FIXTURE_NAME:
            fail(f"expected qualified_name {FIXTURE_NAME!r}, got {entry.get('qualified_name')!r}")
        if entry.get('installed_version') != FIXTURE_VERSION:
            fail(f"expected installed_version {FIXTURE_VERSION!r}, got {entry.get('installed_version')!r}")
        if not entry.get('resolved_release_digest'):
            fail('expected resolved_release_digest to be present')
        if entry.get('install_target') != str(target_dir.resolve()):
            fail(f"expected install_target {str(target_dir.resolve())!r}, got {entry.get('install_target')!r}")

        blocked_target = tmpdir / 'external-auto-target'
        result = run_cli(
            repo,
            ['install', 'by-name', EXTERNAL_SKILL_NAME, str(blocked_target), '--json'],
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'confirmation-required' not in combined:
            fail(f'expected confirmation-required in external auto install failure\n{combined}')
        if blocked_target.exists():
            fail('external auto install unexpectedly created target directory')

        confirm_target = tmpdir / 'external-confirm-target'
        result = run_cli(
            repo,
            [
                'install',
                'by-name',
                EXTERNAL_SKILL_NAME,
                str(confirm_target),
                '--mode',
                'confirm',
                '--json',
            ],
        )
        payload = json.loads(result.stdout)
        if payload.get('state') != 'planned':
            fail(f"expected planned state for confirm mode, got {payload.get('state')!r}")
        if payload.get('requires_confirmation') is not True:
            fail(f"expected requires_confirmation true, got {payload.get('requires_confirmation')!r}")

        add_discovery_fixture(
            repo,
            {
                'name': 'ambiguous-skill',
                'qualified_name': 'alpha/ambiguous-skill',
                'publisher': 'alpha',
                'summary': 'First ambiguous drill skill',
                'source_registry': 'self',
                'source_priority': 100,
                'match_names': ['ambiguous-skill', 'alpha/ambiguous-skill'],
                'default_install_version': '1.0.0',
                'latest_version': '1.0.0',
                'available_versions': ['1.0.0'],
                'agent_compatible': ['codex'],
                'install_requires_confirmation': False,
                'trust_level': 'private',
                'trust_state': 'verified',
                'tags': ['ambiguous'],
                'maturity': 'stable',
                'quality_score': 80,
                'last_verified_at': '2026-03-16T00:00:00Z',
                'capabilities': ['ambiguous-fixture'],
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': ['Need alpha ambiguous fixture'],
                'avoid_when': [],
                'runtime_assumptions': ['Discovery fixture only'],
            },
        )
        add_discovery_fixture(
            repo,
            {
                'name': 'ambiguous-skill',
                'qualified_name': 'beta/ambiguous-skill',
                'publisher': 'beta',
                'summary': 'Second ambiguous drill skill',
                'source_registry': 'self',
                'source_priority': 100,
                'match_names': ['ambiguous-skill', 'beta/ambiguous-skill'],
                'default_install_version': '2.0.0',
                'latest_version': '2.0.0',
                'available_versions': ['2.0.0'],
                'agent_compatible': ['codex'],
                'install_requires_confirmation': False,
                'trust_level': 'private',
                'trust_state': 'verified',
                'tags': ['ambiguous'],
                'maturity': 'stable',
                'quality_score': 79,
                'last_verified_at': '2026-03-16T00:00:00Z',
                'capabilities': ['ambiguous-fixture'],
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': ['Need beta ambiguous fixture'],
                'avoid_when': [],
                'runtime_assumptions': ['Discovery fixture only'],
            },
        )
        ambiguous_target = tmpdir / 'ambiguous-target'
        ambiguous = run_cli(
            repo,
            ['install', 'by-name', 'ambiguous-skill', str(ambiguous_target), '--json'],
            expect=1,
        )
        ambiguous_payload = json.loads(ambiguous.stdout)
        if ambiguous_payload.get('ok') is not False:
            fail(f'expected ambiguous install failure payload, got {ambiguous_payload!r}')
        if ambiguous_payload.get('state') != 'failed':
            fail(f"expected failed ambiguous install state, got {ambiguous_payload.get('state')!r}")
        if ambiguous_payload.get('error_code') != 'ambiguous-skill-name':
            fail(f"expected ambiguous-skill-name, got {ambiguous_payload.get('error_code')!r}")
        if 'qualified_name' not in (ambiguous_payload.get('suggested_action') or ''):
            fail(f'expected suggested_action to mention qualified_name, got {ambiguous_payload!r}')
        explanation = ambiguous_payload.get('explanation') or {}
        if not explanation.get('selection_reason'):
            fail(f'expected explanation on ambiguous install failure, got {ambiguous_payload!r}')

        add_discovery_fixture(
            repo,
            {
                'name': 'incompatible-skill',
                'qualified_name': 'partner/incompatible-skill',
                'publisher': 'partner',
                'summary': 'Incompatible drill skill',
                'source_registry': 'self',
                'source_priority': 100,
                'match_names': ['incompatible-skill', 'partner/incompatible-skill'],
                'default_install_version': '0.1.0',
                'latest_version': '0.1.0',
                'available_versions': ['0.1.0'],
                'agent_compatible': ['openclaw'],
                'install_requires_confirmation': False,
                'trust_level': 'private',
                'trust_state': 'verified',
                'tags': ['incompatible'],
                'maturity': 'beta',
                'quality_score': 40,
                'last_verified_at': '2026-03-16T00:00:00Z',
                'capabilities': ['incompatible-fixture'],
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': ['Need openclaw-only fixture'],
                'avoid_when': [],
                'runtime_assumptions': ['Discovery fixture only'],
            },
        )
        incompatible_target = tmpdir / 'incompatible-target'
        incompatible = run_cli(
            repo,
            [
                'install',
                'by-name',
                'incompatible-skill',
                str(incompatible_target),
                '--target-agent',
                'codex',
                '--json',
            ],
            expect=1,
        )
        incompatible_payload = json.loads(incompatible.stdout)
        if incompatible_payload.get('ok') is not False:
            fail(f'expected incompatible install failure payload, got {incompatible_payload!r}')
        if incompatible_payload.get('error_code') != 'incompatible-target-agent':
            fail(f"expected incompatible-target-agent, got {incompatible_payload.get('error_code')!r}")
        if not incompatible_payload.get('suggested_action'):
            fail(f'expected suggested_action on incompatible install failure, got {incompatible_payload!r}')
        explanation = incompatible_payload.get('explanation') or {}
        if not explanation.get('policy_reasons'):
            fail(f'expected explanation policy_reasons on incompatible install failure, got {incompatible_payload!r}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: install-by-name checks passed')


if __name__ == '__main__':
    main()
