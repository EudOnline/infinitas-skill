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
            'summary': 'Fixture skill for ai-index tests',
            'tags': ['fixture', 'search'],
            'maturity': 'stable',
            'quality_score': 88,
            'capabilities': ['fixture-testing', 'search'],
            'use_when': ['Need to operate inside this repository'],
            'avoid_when': ['Need unrelated public publishing help'],
            'runtime_assumptions': ['A local repo checkout is available'],
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
        'description: Fixture skill for ai-index tests.\n'
        '---\n\n'
        '# Release Fixture\n\n'
        'Used only by automated AI index tests.\n',
        encoding='utf-8',
    )
    (fixture_dir / 'CHANGELOG.md').write_text(
        '# Changelog\n\n'
        f'## {FIXTURE_VERSION} - 2026-03-09\n'
        '- Added AI index fixture release.\n',
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
                    'note': 'Fixture approval for AI index tests',
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
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-ai-index-test-'))
    repo = tmpdir / 'repo'
    origin = tmpdir / 'origin.git'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
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
        ai_index_path = repo / 'catalog' / 'ai-index.json'
        if not ai_index_path.exists():
            fail(f'missing AI index: {ai_index_path}')

        payload = json.loads(ai_index_path.read_text(encoding='utf-8'))
        if payload['install_policy']['mode'] != 'immutable-only':
            fail(f"expected immutable-only install policy, got {payload['install_policy']['mode']!r}")
        if payload['install_policy']['direct_source_install_allowed'] is not False:
            fail('expected direct_source_install_allowed to be false')
        if not payload.get('skills'):
            fail('expected ai-index to contain at least one skill entry')
        entry = next((item for item in payload['skills'] if item.get('name') == FIXTURE_NAME), None)
        if entry is None:
            fail(f'expected ai-index to contain {FIXTURE_NAME}, got {payload.get("skills")!r}')
        if entry.get('publisher') != 'release-test':
            fail(f"expected publisher 'release-test', got {entry.get('publisher')!r}")
        if entry.get('tags') != ['fixture', 'search']:
            fail(f"expected fixture tags, got {entry.get('tags')!r}")
        if entry.get('maturity') != 'stable':
            fail(f"expected maturity 'stable', got {entry.get('maturity')!r}")
        if entry.get('quality_score') != 88:
            fail(f"expected quality_score 88, got {entry.get('quality_score')!r}")
        if entry.get('capabilities') != ['fixture-testing', 'search']:
            fail(f"expected capabilities ['fixture-testing', 'search'], got {entry.get('capabilities')!r}")
        if entry.get('use_when') != ['Need to operate inside this repository']:
            fail(f"expected canonical use_when, got {entry.get('use_when')!r}")
        if entry.get('avoid_when') != ['Need unrelated public publishing help']:
            fail(f"expected canonical avoid_when, got {entry.get('avoid_when')!r}")
        if entry.get('runtime_assumptions') != ['A local repo checkout is available']:
            fail(f"expected canonical runtime_assumptions, got {entry.get('runtime_assumptions')!r}")
        if entry.get('last_verified_at') != '2026-03-12T12:02:00Z':
            fail(f"expected last_verified_at 2026-03-12T12:02:00Z for fresh fixture evidence, got {entry.get('last_verified_at')!r}")
        compatibility = entry.get('compatibility') or {}
        if not isinstance(compatibility.get('verified_support'), dict):
            fail('expected compatibility.verified_support to be an object')
        if entry.get('verified_support') != compatibility.get('verified_support'):
            fail('expected top-level verified_support to match compatibility.verified_support')
        for platform, payload in (entry.get('verified_support') or {}).items():
            if not isinstance(payload, dict):
                fail(f'expected ai-index verified_support payload for {platform!r} to be an object')
            if not isinstance(payload.get('freshness_state'), str) or not payload.get('freshness_state').strip():
                fail(f"expected ai-index verified_support {platform} freshness_state, got {payload!r}")
        if not isinstance(entry.get('trust_state'), str) or not entry.get('trust_state').strip():
            fail(f"expected trust_state to be a non-empty string, got {entry.get('trust_state')!r}")
        versions = entry.get('versions') or {}
        if FIXTURE_VERSION not in versions:
            fail(f'expected version {FIXTURE_VERSION!r} in ai-index versions')
        version_entry = versions[FIXTURE_VERSION]
        for field in ['manifest_path', 'distribution_manifest_path', 'bundle_path', 'bundle_sha256', 'attestation_path']:
            if not version_entry.get(field):
                fail(f'missing version field {field!r}')
        if not isinstance(version_entry.get('attestation_formats'), list) or not version_entry.get('attestation_formats'):
            fail(f"expected attestation_formats for version entry, got {version_entry.get('attestation_formats')!r}")
        if not isinstance(version_entry.get('trust_state'), str) or not version_entry.get('trust_state').strip():
            fail(f"expected version trust_state to be non-empty, got {version_entry.get('trust_state')!r}")

        interop = ((entry.get('interop') or {}).get('openclaw') or {})
        if interop.get('import_supported') is not True:
            fail(f"expected interop.openclaw.import_supported=true, got {interop.get('import_supported')!r}")
        if interop.get('export_supported') is not True:
            fail(f"expected interop.openclaw.export_supported=true, got {interop.get('export_supported')!r}")
        if interop.get('runtime_targets') != ['~/.openclaw/skills', '~/.openclaw/workspace/skills']:
            fail(f"unexpected runtime_targets: {interop.get('runtime_targets')!r}")

        original_ai_index = json.loads(ai_index_path.read_text(encoding='utf-8'))
        target = next((item for item in original_ai_index['skills'] if item.get('name') == FIXTURE_NAME), None)
        if target is None:
            fail(f'expected mutable ai-index entry for {FIXTURE_NAME}')
        target['default_install_version'] = '9.9.9'
        write_json(ai_index_path, original_ai_index)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'default_install_version' not in combined:
            fail(f'expected validation failure mentioning default_install_version\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        rebuilt_payload = json.loads(ai_index_path.read_text(encoding='utf-8'))
        rebuilt_entry = next((item for item in rebuilt_payload['skills'] if item.get('name') == FIXTURE_NAME), None)
        rebuilt_entry['versions'][FIXTURE_VERSION]['distribution_manifest_path'] = '/tmp/manifest.json'
        write_json(ai_index_path, rebuilt_payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'distribution_manifest_path' not in combined:
            fail(f'expected validation failure mentioning distribution_manifest_path\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        rebuilt_payload = json.loads(ai_index_path.read_text(encoding='utf-8'))
        rebuilt_entry = next((item for item in rebuilt_payload['skills'] if item.get('name') == FIXTURE_NAME), None)
        rebuilt_entry['versions'][FIXTURE_VERSION]['attestation_formats'] = 'ssh'
        write_json(ai_index_path, rebuilt_payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'attestation_formats' not in combined:
            fail(f'expected validation failure mentioning attestation_formats\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        rebuilt_payload = json.loads(ai_index_path.read_text(encoding='utf-8'))
        rebuilt_entry = next((item for item in rebuilt_payload['skills'] if item.get('name') == FIXTURE_NAME), None)
        rebuilt_entry['quality_score'] = 'high'
        write_json(ai_index_path, rebuilt_payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'quality_score' not in combined:
            fail(f'expected validation failure mentioning quality_score\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)
        rebuilt_payload = json.loads(ai_index_path.read_text(encoding='utf-8'))
        rebuilt_entry = next((item for item in rebuilt_payload['skills'] if item.get('name') == FIXTURE_NAME), None)
        rebuilt_entry['runtime_assumptions'] = 'repo checkout required'
        write_json(ai_index_path, rebuilt_payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'runtime_assumptions' not in combined:
            fail(f'expected validation failure mentioning runtime_assumptions\n{combined}')

        run([str(repo / 'scripts' / 'build-catalog.sh')], cwd=repo)

        skill_md_path = repo / 'skills' / 'active' / FIXTURE_NAME / 'SKILL.md'
        original_skill_md = skill_md_path.read_text(encoding='utf-8')
        skill_md_path.write_text(original_skill_md.replace(f'name: {FIXTURE_NAME}', 'name: wrong-name', 1), encoding='utf-8')
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'frontmatter name' not in combined:
            fail(f'expected validation failure mentioning frontmatter name\n{combined}')

        skill_md_path.write_text(original_skill_md.replace('description: Fixture skill for ai-index tests.', 'description:', 1), encoding='utf-8')
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'frontmatter description' not in combined:
            fail(f'expected validation failure mentioning frontmatter description\n{combined}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: ai-index checks passed')


if __name__ == '__main__':
    main()
