#!/usr/bin/env python3
import json
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


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def discovery_index_payload():
    return {
        'schema_version': 1,
        'generated_at': '2026-03-12T00:00:00Z',
        'default_registry': 'self',
        'sources': [
            {
                'name': 'self',
                'kind': 'git',
                'priority': 100,
                'trust_level': 'private',
                'root': '/tmp/self',
                'status': 'ready',
            },
            {
                'name': 'external-demo',
                'kind': 'local',
                'priority': 50,
                'trust_level': 'trusted',
                'root': '/tmp/external-demo',
                'status': 'ready',
            },
        ],
        'resolution_policy': {
            'private_registry_first': True,
            'external_requires_confirmation': True,
            'auto_install_mutable_sources': False,
        },
        'skills': [
            {
                'name': 'demo-skill',
                'qualified_name': 'lvxiaoer/demo-skill',
                'publisher': 'lvxiaoer',
                'summary': 'Private demo skill',
                'source_registry': 'self',
                'source_priority': 100,
                'match_names': ['demo-skill', 'lvxiaoer/demo-skill'],
                'default_install_version': '1.2.3',
                'latest_version': '1.2.3',
                'available_versions': ['1.2.3'],
                'agent_compatible': ['openclaw', 'claude-code', 'codex'],
                'install_requires_confirmation': False,
                'trust_level': 'private',
                'trust_state': 'verified',
                'tags': ['private', 'demo'],
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': ['Need private demo skill'],
                'avoid_when': [],
            },
            {
                'name': 'external-only-skill',
                'qualified_name': 'partner/external-only-skill',
                'publisher': 'partner',
                'summary': 'External only skill',
                'source_registry': 'external-demo',
                'source_priority': 50,
                'match_names': ['external-only-skill', 'partner/external-only-skill'],
                'default_install_version': '0.9.0',
                'latest_version': '0.9.0',
                'available_versions': ['0.9.0'],
                'agent_compatible': ['openclaw', 'claude-code', 'codex'],
                'install_requires_confirmation': True,
                'trust_level': 'trusted',
                'trust_state': 'attested',
                'tags': ['external', 'demo'],
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': ['Need external coverage'],
                'avoid_when': [],
            },
            {
                'name': 'ambiguous-skill',
                'qualified_name': 'alpha/ambiguous-skill',
                'publisher': 'alpha',
                'summary': 'First ambiguous private skill',
                'source_registry': 'self',
                'source_priority': 100,
                'match_names': ['alpha/ambiguous-skill', 'ambiguous-skill'],
                'default_install_version': '1.0.0',
                'latest_version': '1.0.0',
                'available_versions': ['1.0.0'],
                'agent_compatible': ['codex'],
                'install_requires_confirmation': False,
                'trust_level': 'private',
                'trust_state': 'verified',
                'tags': ['ambiguous'],
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': [],
                'avoid_when': [],
            },
            {
                'name': 'ambiguous-skill',
                'qualified_name': 'beta/ambiguous-skill',
                'publisher': 'beta',
                'summary': 'Second ambiguous private skill',
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
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': [],
                'avoid_when': [],
            },
            {
                'name': 'incompatible-skill',
                'qualified_name': 'partner/incompatible-skill',
                'publisher': 'partner',
                'summary': 'External incompatible skill',
                'source_registry': 'external-demo',
                'source_priority': 50,
                'match_names': ['incompatible-skill', 'partner/incompatible-skill'],
                'default_install_version': '0.1.0',
                'latest_version': '0.1.0',
                'available_versions': ['0.1.0'],
                'agent_compatible': ['openclaw'],
                'install_requires_confirmation': True,
                'trust_level': 'trusted',
                'trust_state': 'attested',
                'tags': ['external'],
                'verified_support': {},
                'attestation_formats': ['ssh'],
                'use_when': [],
                'avoid_when': [],
            },
        ],
    }


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-resolve-skill-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    write_json(repo / 'catalog' / 'discovery-index.json', discovery_index_payload())
    return tmpdir, repo


def main():
    tmpdir, repo = prepare_repo()
    try:
        payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), 'demo-skill'], cwd=repo).stdout)
        if payload.get('state') != 'resolved-private':
            fail(f"expected resolved-private, got {payload.get('state')!r}")
        if payload.get('requires_confirmation') is not False:
            fail(f"expected requires_confirmation false, got {payload.get('requires_confirmation')!r}")
        resolved = payload.get('resolved') or {}
        if resolved.get('source_registry') != 'self':
            fail(f"expected resolved source_registry self, got {resolved.get('source_registry')!r}")

        payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), 'external-only-skill'], cwd=repo).stdout)
        if payload.get('state') != 'resolved-external':
            fail(f"expected resolved-external, got {payload.get('state')!r}")
        if payload.get('requires_confirmation') is not True:
            fail(f"expected requires_confirmation true, got {payload.get('requires_confirmation')!r}")

        payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), 'ambiguous-skill'], cwd=repo).stdout)
        if payload.get('state') != 'ambiguous':
            fail(f"expected ambiguous, got {payload.get('state')!r}")
        if len(payload.get('candidates') or []) != 2:
            fail(f"expected 2 ambiguous candidates, got {len(payload.get('candidates') or [])}")

        payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), 'demo-skill', '--target-agent', 'codex'], cwd=repo).stdout)
        if payload.get('state') == 'incompatible':
            fail(f"expected codex-compatible demo-skill, got {payload!r}")

        payload = json.loads(run([str(repo / 'scripts' / 'resolve-skill.sh'), 'incompatible-skill', '--target-agent', 'codex'], cwd=repo).stdout)
        if payload.get('state') != 'incompatible':
            fail(f"expected incompatible state, got {payload.get('state')!r}")
    finally:
        shutil.rmtree(tmpdir)

    print('OK: resolve-skill checks passed')


if __name__ == '__main__':
    main()
