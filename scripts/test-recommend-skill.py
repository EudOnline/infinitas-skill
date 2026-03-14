#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
QUALIFIED_NAME = 'lvxiaoer/operate-infinitas-skill'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0):
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    except FileNotFoundError as exc:
        fail(f'missing command {command[0]!r}: {exc}')
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


def contains_absolute_path(value):
    if isinstance(value, str):
        return value.startswith('/') or value.startswith('C:\\')
    if isinstance(value, dict):
        return any(contains_absolute_path(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_absolute_path(item) for item in value)
    return False


def scenario_recommend_returns_ranked_fields_for_real_catalog():
    payload = json.loads(
        run(['./scripts/recommend-skill.sh', 'operate in this repo', '--target-agent', 'codex'], cwd=ROOT).stdout
    )
    results = payload.get('results') or []
    if not results:
        fail('expected at least one recommendation result')
    top = results[0]
    for key in [
        'qualified_name',
        'score',
        'recommendation_reason',
        'ranking_factors',
        'trust_state',
        'verified_support',
    ]:
        if key not in top:
            fail(f'missing recommendation field {key!r}')
    factors = top.get('ranking_factors') or {}
    for key in ['match_strength', 'compatibility', 'trust', 'quality', 'verification_freshness']:
        if key not in factors:
            fail(f'missing ranking_factors field {key!r}')
    if top.get('qualified_name') != QUALIFIED_NAME:
        fail(f"expected top recommendation {QUALIFIED_NAME!r}, got {top.get('qualified_name')!r}")
    explanation = payload.get('explanation') or {}
    if not isinstance(explanation.get('winner_reason'), str) or not explanation.get('winner_reason').strip():
        fail(f"expected top-level winner_reason, got {explanation.get('winner_reason')!r}")
    if explanation.get('winner') != QUALIFIED_NAME:
        fail(f"expected explanation winner {QUALIFIED_NAME!r}, got {explanation.get('winner')!r}")
    if contains_absolute_path(payload):
        fail(f'expected recommendation payload to avoid raw filesystem paths\n{json.dumps(payload, ensure_ascii=False, indent=2)}')


def discovery_index_payload():
    return {
        'schema_version': 1,
        'generated_at': '2026-03-15T00:00:00Z',
        'default_registry': 'self',
        'sources': [
            {'name': 'self', 'kind': 'git', 'priority': 100, 'trust_level': 'private', 'root': '.', 'status': 'ready'},
            {'name': 'external-demo', 'kind': 'local', 'priority': 50, 'trust_level': 'trusted', 'root': '../external-demo', 'status': 'ready'},
        ],
        'resolution_policy': {
            'private_registry_first': True,
            'external_requires_confirmation': True,
            'auto_install_mutable_sources': False,
        },
        'skills': [
            {
                'name': 'ops-private',
                'qualified_name': 'team/ops-private',
                'publisher': 'team',
                'summary': 'Operate safely inside this repository',
                'source_registry': 'self',
                'source_priority': 100,
                'match_names': ['ops-private', 'team/ops-private'],
                'default_install_version': '1.2.3',
                'latest_version': '1.2.3',
                'available_versions': ['1.2.3'],
                'agent_compatible': ['codex'],
                'install_requires_confirmation': False,
                'trust_level': 'private',
                'trust_state': 'verified',
                'tags': ['operations', 'repo'],
                'verified_support': {'codex': {'state': 'adapted', 'checked_at': '2026-03-15T00:00:00Z'}},
                'attestation_formats': ['ssh'],
                'use_when': ['Need to operate in this repo'],
                'avoid_when': [],
                'maturity': 'stable',
                'quality_score': 92,
                'last_verified_at': '2026-03-15T00:00:00Z',
                'capabilities': ['repo-operations', 'release'],
            },
            {
                'name': 'ops-external',
                'qualified_name': 'partner/ops-external',
                'publisher': 'partner',
                'summary': 'External operations helper',
                'source_registry': 'external-demo',
                'source_priority': 50,
                'match_names': ['ops-external', 'partner/ops-external'],
                'default_install_version': '0.9.0',
                'latest_version': '0.9.0',
                'available_versions': ['0.9.0'],
                'agent_compatible': ['codex'],
                'install_requires_confirmation': True,
                'trust_level': 'trusted',
                'trust_state': 'attested',
                'tags': ['operations'],
                'verified_support': {'codex': {'state': 'adapted', 'checked_at': '2026-03-10T00:00:00Z'}},
                'attestation_formats': ['ssh'],
                'use_when': ['Need repo operations'],
                'avoid_when': [],
                'maturity': 'beta',
                'quality_score': 61,
                'last_verified_at': '2026-03-10T00:00:00Z',
                'capabilities': ['repo-operations'],
            },
            {
                'name': 'notes-helper',
                'qualified_name': 'partner/notes-helper',
                'publisher': 'partner',
                'summary': 'Documentation helper',
                'source_registry': 'external-demo',
                'source_priority': 50,
                'match_names': ['notes-helper', 'partner/notes-helper'],
                'default_install_version': '0.1.0',
                'latest_version': '0.1.0',
                'available_versions': ['0.1.0'],
                'agent_compatible': ['openclaw'],
                'install_requires_confirmation': True,
                'trust_level': 'trusted',
                'trust_state': 'attested',
                'tags': ['docs'],
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': ['Need docs tooling'],
                'avoid_when': [],
                'maturity': 'experimental',
                'quality_score': 40,
                'last_verified_at': None,
                'capabilities': ['docs'],
            },
        ],
    }


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-recommend-skill-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    write_json(repo / 'catalog' / 'discovery-index.json', discovery_index_payload())
    return tmpdir, repo


def scenario_recommend_prefers_private_high_quality_match():
    tmpdir, repo = prepare_repo()
    try:
        payload = json.loads(
            run(['./scripts/recommend-skill.sh', 'Need repo operations', '--target-agent', 'codex'], cwd=repo).stdout
        )
        results = payload.get('results') or []
        if len(results) < 2:
            fail(f'expected at least two ranked recommendation results, got {len(results)}')
        top = results[0]
        external = next((item for item in results if item.get('qualified_name') == 'partner/ops-external'), None)
        if top.get('qualified_name') != 'team/ops-private':
            fail(f"expected private candidate to outrank external candidate, got {top.get('qualified_name')!r}")
        if not external:
            fail('expected ranked results to include external candidate')
        if external.get('install_requires_confirmation') is not True:
            fail(f"expected external recommendation to require confirmation, got {external.get('install_requires_confirmation')!r}")
        explanation = payload.get('explanation') or {}
        if explanation.get('runner_up') != 'partner/ops-external':
            fail(f"expected runner_up 'partner/ops-external', got {explanation.get('runner_up')!r}")
        if contains_absolute_path(payload):
            fail(f'expected recommendation payload to avoid raw filesystem paths\n{json.dumps(payload, ensure_ascii=False, indent=2)}')
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_recommend_returns_ranked_fields_for_real_catalog()
    scenario_recommend_prefers_private_high_quality_match()
    print('OK: recommend-skill checks passed')


if __name__ == '__main__':
    main()
