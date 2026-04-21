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

from infinitas_skill.discovery.index import build_discovery_index  # noqa: E402
from infinitas_skill.testing.env import build_regression_test_env

FIXTURE_NAME = 'release-fixture'
FIXTURE_VERSION = '1.2.3'
EXTERNAL_REGISTRY_NAME = 'external-demo'
EXTERNAL_SKILL_NAME = 'partner-skill'
EXTERNAL_SKILL_VERSION = '0.9.0'
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


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def normalized_catalog_payload(path: Path):
    payload = load_json(path)
    payload.pop('generated_at', None)
    return payload


def assert_discovery_payload_stable_across_roots():
    local_ai_index = {
        'skills': [
            {
                'name': FIXTURE_NAME,
                'qualified_name': FIXTURE_NAME,
                'publisher': 'release-test',
                'summary': 'Fixture skill for discovery-index tests',
                'tags': ['fixture', 'search'],
                'agent_compatible': ['codex'],
                'verified_support': {
                    'codex': {
                        'state': 'adapted',
                        'checked_at': '2026-03-14T00:00:00Z',
                        'freshness_state': 'fresh',
                        'freshness_reason': 'not-applicable',
                        'contract_last_verified': '2026-03-12',
                    }
                },
                'trust_state': 'verified',
                'default_install_version': FIXTURE_VERSION,
                'latest_version': FIXTURE_VERSION,
                'available_versions': [FIXTURE_VERSION],
                'maturity': 'stable',
                'quality_score': 91,
                'last_verified_at': '2026-03-14T00:00:00Z',
                'capabilities': ['fixture-testing', 'search'],
                'versions': {
                    FIXTURE_VERSION: {
                        'attestation_formats': ['ssh'],
                        'distribution_manifest_path': f'catalog/distributions/{FIXTURE_NAME}/{FIXTURE_VERSION}/manifest.json',
                    }
                },
                'use_when': ['Need to operate inside this repository'],
                'avoid_when': ['Need unrelated public publishing help'],
                'runtime_assumptions': ['A local repo checkout is available'],
            }
        ]
    }
    registry_config = {
        'default_registry': 'self',
        'registries': [
            {
                'name': 'self',
                'kind': 'git',
                'local_path': '.',
                'priority': 100,
                'enabled': True,
                'trust': 'private',
                'update_policy': {'mode': 'local-only'},
            }
        ],
    }
    primary = build_discovery_index(root=Path('/tmp/primary-repo'), local_ai_index=local_ai_index, registry_config=registry_config)
    linked = build_discovery_index(root=Path('/tmp/primary-repo/.worktrees/linked'), local_ai_index=local_ai_index, registry_config=registry_config)
    primary.pop('generated_at', None)
    linked.pop('generated_at', None)
    if primary != linked:
        fail('expected discovery-index payload to stay stable across linked worktrees')
    self_source = next((item for item in primary.get('sources') or [] if item.get('name') == 'self'), None)
    if not self_source:
        fail('expected discovery-index to include self source entry')
    if self_source.get('root') != '.':
        fail(f"expected self source root '.', got {self_source.get('root')!r}")
    fixture = next((item for item in primary.get('skills') or [] if item.get('name') == FIXTURE_NAME), None)
    if fixture is None:
        fail(f'expected stable discovery payload to contain {FIXTURE_NAME}')
    if fixture.get('publisher') != 'release-test':
        fail(f"expected stable publisher 'release-test', got {fixture.get('publisher')!r}")
    if fixture.get('tags') != ['fixture', 'search']:
        fail(f"expected stable tags ['fixture', 'search'], got {fixture.get('tags')!r}")
    if fixture.get('trust_state') != 'verified':
        fail(f"expected stable trust_state 'verified', got {fixture.get('trust_state')!r}")
    if fixture.get('verified_support') != {
        'codex': {
            'state': 'adapted',
            'checked_at': '2026-03-14T00:00:00Z',
            'freshness_state': 'fresh',
            'freshness_reason': 'not-applicable',
            'contract_last_verified': '2026-03-12',
        }
    }:
        fail(f"expected stable verified_support, got {fixture.get('verified_support')!r}")
    if fixture.get('attestation_formats') != ['ssh']:
        fail(f"expected stable attestation_formats ['ssh'], got {fixture.get('attestation_formats')!r}")
    if fixture.get('maturity') != 'stable':
        fail(f"expected stable maturity 'stable', got {fixture.get('maturity')!r}")
    if fixture.get('quality_score') != 91:
        fail(f"expected stable quality_score 91, got {fixture.get('quality_score')!r}")
    if fixture.get('last_verified_at') != '2026-03-14T00:00:00Z':
        fail(f"expected stable last_verified_at, got {fixture.get('last_verified_at')!r}")
    if fixture.get('capabilities') != ['fixture-testing', 'search']:
        fail(f"expected stable capabilities, got {fixture.get('capabilities')!r}")
    if fixture.get('use_when') != ['Need to operate inside this repository']:
        fail(f"expected stable use_when, got {fixture.get('use_when')!r}")
    if fixture.get('avoid_when') != ['Need unrelated public publishing help']:
        fail(f"expected stable avoid_when, got {fixture.get('avoid_when')!r}")
    if fixture.get('runtime_assumptions') != ['A local repo checkout is available']:
        fail(f"expected stable runtime_assumptions, got {fixture.get('runtime_assumptions')!r}")


def make_env(extra=None):
    return build_regression_test_env(ROOT, extra=extra, env=os.environ.copy())


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
            'summary': 'Fixture skill for discovery-index tests',
            'tags': ['fixture', 'search'],
            'maturity': 'stable',
            'quality_score': 91,
            'capabilities': ['fixture-testing', 'search'],
            'use_when': ['Need to operate inside this repository'],
            'avoid_when': ['Need unrelated public publishing help'],
            'runtime_assumptions': ['A local repo checkout is available'],
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
        'description: Fixture skill for discovery-index tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated discovery-index tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-12\n'
        '- Added discovery-index fixture release.\n',
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
                    'note': 'Fixture approval for discovery-index tests',
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
                'summary': 'External fixture skill',
                'tags': ['external', 'fixture'],
                'use_when': ['Need external fixture coverage'],
                'avoid_when': ['Testing unrelated behavior'],
                'runtime_assumptions': ['A trusted external registry is configured'],
                'agent_compatible': ['openclaw', 'claude-code', 'codex'],
                'verified_support': {
                    'codex': {
                        'state': 'adapted',
                        'checked_at': '2026-03-12T00:00:00Z',
                        'freshness_state': 'stale',
                        'freshness_reason': 'age-expired',
                        'contract_last_verified': '2026-03-12',
                    }
                },
                'trust_state': 'attested',
                'default_install_version': EXTERNAL_SKILL_VERSION,
                'latest_version': EXTERNAL_SKILL_VERSION,
                'available_versions': [EXTERNAL_SKILL_VERSION],
                'maturity': 'beta',
                'quality_score': 63,
                'last_verified_at': '2026-03-12T00:00:00Z',
                'capabilities': ['external-fixture'],
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
                        'resolution': {
                            'preferred_source': 'distribution-manifest',
                            'fallback_allowed': False,
                        },
                    }
                },
            }
        ],
    }


def configure_external_registry(repo: Path, external_repo: Path):
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
            'notes': 'External fixture registry for discovery-index tests',
        }
    )
    write_json(registry_path, payload)


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-discovery-index-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    external_repo = tmpdir / EXTERNAL_REGISTRY_NAME
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

    external_repo.mkdir(parents=True, exist_ok=True)
    write_json(external_repo / 'catalog' / 'ai-index.json', external_ai_index_payload())
    configure_external_registry(repo, external_repo)
    run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
    run(['git', 'add', 'config/registry-sources.json', 'catalog'], cwd=repo)
    run(['git', 'commit', '-m', 'add external registry fixture'], cwd=repo)
    run(['git', 'push'], cwd=repo)
    return tmpdir, repo


def release_fixture(repo: Path):
    run(
        [str(repo / 'scripts' / 'release-skill.sh'), FIXTURE_NAME, '--push-tag', '--write-provenance'],
        cwd=repo,
        env=make_env(),
    )


def main():
    tmpdir, repo = prepare_repo()
    try:
        release_fixture(repo)
        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        discovery_index_path = repo / 'catalog' / 'discovery-index.json'
        if not discovery_index_path.exists():
            fail(f'missing discovery index: {discovery_index_path}')

        payload = json.loads(discovery_index_path.read_text(encoding='utf-8'))
        if payload.get('default_registry') != 'self':
            fail(f"expected default_registry 'self', got {payload.get('default_registry')!r}")
        policy = payload.get('resolution_policy') or {}
        if policy.get('private_registry_first') is not True:
            fail('expected private_registry_first=true')
        if not payload.get('skills'):
            fail('expected discovery-index to contain at least one skill entry')
        first = payload['skills'][0]
        if not first.get('qualified_name'):
            fail('expected first skill to have qualified_name')
        if not first.get('publisher'):
            fail('expected first skill to have publisher')
        if not first.get('source_registry'):
            fail('expected first skill to have source_registry')
        if not isinstance(first.get('match_names'), list):
            fail('expected first skill match_names to be a list')
        if not isinstance(first.get('install_requires_confirmation'), bool):
            fail('expected first skill install_requires_confirmation to be a bool')
        if not isinstance(first.get('tags'), list):
            fail('expected first skill tags to be a list')
        if not isinstance(first.get('verified_support'), dict):
            fail('expected first skill verified_support to be an object')
        if not isinstance(first.get('attestation_formats'), list) or not first.get('attestation_formats'):
            fail('expected first skill attestation_formats to be a non-empty list')
        if not isinstance(first.get('trust_state'), str) or not first.get('trust_state').strip():
            fail('expected first skill trust_state to be a non-empty string')
        if not isinstance(first.get('maturity'), str) or not first.get('maturity').strip():
            fail('expected first skill maturity to be a non-empty string')
        if not isinstance(first.get('quality_score'), int):
            fail('expected first skill quality_score to be an int')
        if first.get('last_verified_at') is not None and not isinstance(first.get('last_verified_at'), str):
            fail('expected first skill last_verified_at to be a string or null')
        if not isinstance(first.get('capabilities'), list):
            fail('expected first skill capabilities to be a list')
        if not isinstance(first.get('runtime_assumptions'), list):
            fail('expected first skill runtime_assumptions to be a list')

        assert_discovery_payload_stable_across_roots()

        fixture = next((item for item in payload['skills'] if item.get('name') == FIXTURE_NAME), None)
        if fixture is None:
            fail(f'expected discovery-index to contain local fixture {FIXTURE_NAME}')
        if fixture.get('publisher') != 'release-test':
            fail(f"expected local publisher 'release-test', got {fixture.get('publisher')!r}")
        if fixture.get('tags') != ['fixture', 'search']:
            fail(f"expected local tags ['fixture', 'search'], got {fixture.get('tags')!r}")
        if fixture.get('maturity') != 'stable':
            fail(f"expected local maturity 'stable', got {fixture.get('maturity')!r}")
        if fixture.get('quality_score') != 91:
            fail(f"expected local quality_score 91, got {fixture.get('quality_score')!r}")
        if fixture.get('capabilities') != ['fixture-testing', 'search']:
            fail(f"expected local capabilities, got {fixture.get('capabilities')!r}")
        if fixture.get('use_when') != ['Need to operate inside this repository']:
            fail(f"expected local use_when, got {fixture.get('use_when')!r}")
        if fixture.get('avoid_when') != ['Need unrelated public publishing help']:
            fail(f"expected local avoid_when, got {fixture.get('avoid_when')!r}")
        if fixture.get('runtime_assumptions') != ['A local repo checkout is available']:
            fail(f"expected local runtime_assumptions, got {fixture.get('runtime_assumptions')!r}")

        external = next((item for item in payload['skills'] if item.get('name') == EXTERNAL_SKILL_NAME), None)
        if external is None:
            fail(f'expected discovery-index to contain external fixture {EXTERNAL_SKILL_NAME}')
        if external.get('publisher') != 'partner':
            fail(f"expected external publisher 'partner', got {external.get('publisher')!r}")
        if external.get('tags') != ['external', 'fixture']:
            fail(f"expected external tags ['external', 'fixture'], got {external.get('tags')!r}")
        if external.get('trust_state') != 'attested':
            fail(f"expected external trust_state 'attested', got {external.get('trust_state')!r}")
        if external.get('verified_support') != {
            'codex': {
                'state': 'adapted',
                'checked_at': '2026-03-12T00:00:00Z',
                'freshness_state': 'stale',
                'freshness_reason': 'age-expired',
                'contract_last_verified': '2026-03-12',
            }
        }:
            fail(f"expected external verified_support, got {external.get('verified_support')!r}")
        if external.get('attestation_formats') != ['ssh']:
            fail(f"expected external attestation_formats ['ssh'], got {external.get('attestation_formats')!r}")
        if external.get('maturity') != 'beta':
            fail(f"expected external maturity 'beta', got {external.get('maturity')!r}")
        if external.get('quality_score') != 63:
            fail(f"expected external quality_score 63, got {external.get('quality_score')!r}")
        if external.get('last_verified_at') != '2026-03-12T00:00:00Z':
            fail(f"expected external last_verified_at, got {external.get('last_verified_at')!r}")
        if external.get('capabilities') != ['external-fixture']:
            fail(f"expected external capabilities, got {external.get('capabilities')!r}")
        if external.get('use_when') != ['Need external fixture coverage']:
            fail(f"expected external use_when, got {external.get('use_when')!r}")
        if external.get('avoid_when') != ['Testing unrelated behavior']:
            fail(f"expected external avoid_when, got {external.get('avoid_when')!r}")
        if external.get('runtime_assumptions') != ['A trusted external registry is configured']:
            fail(f"expected external runtime_assumptions, got {external.get('runtime_assumptions')!r}")

        self_source = next((item for item in payload.get('sources') or [] if item.get('name') == 'self'), None)
        if not self_source:
            fail('expected discovery-index to include self source entry')
        if self_source.get('root') != '.':
            fail(f"expected self source root '.', got {self_source.get('root')!r}")

        broken = load_json(discovery_index_path)
        broken['skills'][0]['match_names'] = 'not-a-list'
        write_json(discovery_index_path, broken)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'match_names' not in combined:
            fail(f'expected validation failure mentioning match_names\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        broken = load_json(discovery_index_path)
        broken['skills'][0]['attestation_formats'] = 'ssh'
        write_json(discovery_index_path, broken)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'attestation_formats' not in combined:
            fail(f'expected validation failure mentioning attestation_formats\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        broken = load_json(discovery_index_path)
        broken['skills'][0]['trust_state'] = ''
        write_json(discovery_index_path, broken)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'trust_state' not in combined:
            fail(f'expected validation failure mentioning trust_state\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        broken = load_json(discovery_index_path)
        broken['skills'][0]['quality_score'] = 'high'
        write_json(discovery_index_path, broken)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'quality_score' not in combined:
            fail(f'expected validation failure mentioning quality_score\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        broken = load_json(discovery_index_path)
        broken['skills'][0]['runtime_assumptions'] = 'repo checkout required'
        write_json(discovery_index_path, broken)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'runtime_assumptions' not in combined:
            fail(f'expected validation failure mentioning runtime_assumptions\n{combined}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: discovery-index checks passed')


if __name__ == '__main__':
    main()
