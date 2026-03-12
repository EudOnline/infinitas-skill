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
FIXTURE_VERSION = '1.2.3'
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
                        'bundle_path': f'catalog/distributions/_legacy/{EXTERNAL_SKILL_NAME}/{EXTERNAL_SKILL_VERSION}/bundle.tar.gz',
                        'bundle_sha256': 'deadbeef',
                        'attestation_path': f'catalog/provenance/{EXTERNAL_SKILL_NAME}-{EXTERNAL_SKILL_VERSION}.json',
                        'attestation_signature_path': None,
                        'published_at': '2026-03-12T00:00:00Z',
                        'stability': 'stable',
                        'installable': True,
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
        run([str(repo / 'scripts' / 'install-by-name.sh'), FIXTURE_NAME, str(target_dir)], cwd=repo)
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
        result = run(
            [str(repo / 'scripts' / 'install-by-name.sh'), EXTERNAL_SKILL_NAME, str(blocked_target)],
            cwd=repo,
            expect=1,
        )
        combined = result.stdout + result.stderr
        if 'confirmation-required' not in combined:
            fail(f'expected confirmation-required in external auto install failure\n{combined}')
        if blocked_target.exists():
            fail('external auto install unexpectedly created target directory')

        confirm_target = tmpdir / 'external-confirm-target'
        result = run(
            [str(repo / 'scripts' / 'install-by-name.sh'), EXTERNAL_SKILL_NAME, str(confirm_target), '--mode', 'confirm'],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        if payload.get('state') != 'planned':
            fail(f"expected planned state for confirm mode, got {payload.get('state')!r}")
        if payload.get('requires_confirmation') is not True:
            fail(f"expected requires_confirmation true, got {payload.get('requires_confirmation')!r}")
    finally:
        shutil.rmtree(tmpdir)

    print('OK: install-by-name checks passed')


if __name__ == '__main__':
    main()
