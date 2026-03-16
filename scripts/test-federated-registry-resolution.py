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


def registry_config():
    return {
        '$schema': '../schemas/registry-sources.schema.json',
        'default_registry': 'self',
        'registries': [
            {
                'name': 'self',
                'kind': 'git',
                'url': 'https://github.com/EudOnline/infinitas-skill.git',
                'local_path': '.',
                'branch': 'main',
                'priority': 100,
                'enabled': True,
                'trust': 'private',
                'allowed_hosts': ['github.com'],
                'allowed_refs': ['refs/heads/main'],
                'pin': {
                    'mode': 'branch',
                    'value': 'main',
                },
                'update_policy': {
                    'mode': 'local-only',
                },
            },
            {
                'name': 'upstream-fed',
                'kind': 'git',
                'url': 'https://github.com/example/upstream-fed.git',
                'priority': 80,
                'enabled': True,
                'trust': 'trusted',
                'allowed_hosts': ['github.com'],
                'allowed_refs': ['refs/tags/v1.0.0'],
                'pin': {
                    'mode': 'tag',
                    'value': 'v1.0.0',
                },
                'update_policy': {
                    'mode': 'pinned',
                },
                'federation': {
                    'mode': 'federated',
                    'allowed_publishers': ['partner'],
                    'publisher_map': {
                        'partner': 'partner-labs',
                    },
                    'require_immutable_artifacts': True,
                },
            },
            {
                'name': 'upstream-mirror',
                'kind': 'git',
                'url': 'https://github.com/example/upstream-mirror.git',
                'priority': 120,
                'enabled': True,
                'trust': 'trusted',
                'allowed_hosts': ['github.com'],
                'allowed_refs': ['refs/tags/v1.0.0'],
                'pin': {
                    'mode': 'tag',
                    'value': 'v1.0.0',
                },
                'update_policy': {
                    'mode': 'pinned',
                },
                'federation': {
                    'mode': 'mirror',
                    'allowed_publishers': ['partner'],
                    'publisher_map': {
                        'partner': 'partner-labs',
                    },
                    'require_immutable_artifacts': True,
                },
            },
        ],
    }


def upstream_skill_meta():
    return {
        'name': 'demo',
        'publisher': 'partner',
        'qualified_name': 'partner/demo',
        'version': '1.0.0',
        'status': 'active',
        'summary': 'Federated registry fixture skill',
        'distribution': {
            'installable': True,
        },
    }


def write_upstream_registry(repo: Path, registry_name: str):
    reg_root = repo / '.cache' / 'registries' / registry_name
    write_json(reg_root / 'skills' / 'active' / 'demo' / '_meta.json', upstream_skill_meta())


def resolved_payload(stdout: str):
    payload = json.loads(stdout)
    if isinstance(payload, dict) and isinstance(payload.get('resolved'), dict):
        return payload.get('resolved')
    if isinstance(payload, dict):
        return payload
    fail(f'expected JSON object payload, got {payload!r}')


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-federated-resolution-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    write_json(repo / 'config' / 'registry-sources.json', registry_config())
    write_upstream_registry(repo, 'upstream-fed')
    write_upstream_registry(repo, 'upstream-mirror')
    return tmpdir, repo


def scenario_mapped_publisher_resolution():
    tmpdir, repo = prepare_repo()
    try:
        result = run(
            ['python3', 'scripts/resolve-skill-source.py', 'partner-labs/demo', '--registry', 'upstream-fed', '--json'],
            cwd=repo,
        )
        resolved = resolved_payload(result.stdout)
        if resolved.get('publisher') != 'partner-labs':
            fail(f"expected mapped publisher 'partner-labs', got {resolved!r}")
        if resolved.get('qualified_name') != 'partner-labs/demo':
            fail(f"expected mapped qualified_name 'partner-labs/demo', got {resolved!r}")
        if resolved.get('upstream_publisher') != 'partner':
            fail(f"expected upstream publisher 'partner', got {resolved!r}")
        if resolved.get('upstream_qualified_name') != 'partner/demo':
            fail(f"expected upstream qualified_name 'partner/demo', got {resolved!r}")
        if resolved.get('federation_mode') != 'federated':
            fail(f"expected federation_mode 'federated', got {resolved!r}")
        if resolved.get('publisher_mapping_applied') is not True:
            fail(f'expected publisher_mapping_applied true, got {resolved!r}')
    finally:
        shutil.rmtree(tmpdir)


def scenario_mirror_registry_is_not_default_candidate():
    tmpdir, repo = prepare_repo()
    try:
        result = run(
            ['python3', 'scripts/resolve-skill-source.py', 'partner-labs/demo', '--json'],
            cwd=repo,
        )
        resolved = resolved_payload(result.stdout)
        if resolved.get('registry_name') != 'upstream-fed':
            fail(f"expected upstream-fed to win normal resolution, got {resolved!r}")
        if resolved.get('federation_mode') != 'federated':
            fail(f"expected federated resolver candidate, got {resolved!r}")
    finally:
        shutil.rmtree(tmpdir)


def scenario_build_catalog_exports_federation_identity():
    tmpdir, repo = prepare_repo()
    try:
        run(['bash', 'scripts/build-catalog.sh'], cwd=repo)
        payload = json.loads((repo / 'catalog' / 'registries.json').read_text(encoding='utf-8'))
        registries = {item.get('name'): item for item in payload.get('registries') or []}
        fed = registries.get('upstream-fed')
        mirror = registries.get('upstream-mirror')
        if fed is None or mirror is None:
            fail(f'expected federated and mirror registries in catalog export, got {sorted(registries)!r}')
        if fed.get('resolved_federation_mode') != 'federated':
            fail(f"expected resolved_federation_mode 'federated', got {fed!r}")
        if fed.get('resolved_allowed_publishers') != ['partner']:
            fail(f"expected resolved_allowed_publishers ['partner'], got {fed!r}")
        if fed.get('resolved_publisher_map') != {'partner': 'partner-labs'}:
            fail(f"expected resolved_publisher_map to preserve partner mapping, got {fed!r}")
        if fed.get('resolved_require_immutable_artifacts') is not True:
            fail(f"expected resolved_require_immutable_artifacts true, got {fed!r}")
        if mirror.get('resolved_federation_mode') != 'mirror':
            fail(f"expected resolved_federation_mode 'mirror', got {mirror!r}")
    finally:
        shutil.rmtree(tmpdir)


def main():
    scenario_mapped_publisher_resolution()
    scenario_mirror_registry_is_not_default_candidate()
    scenario_build_catalog_exports_federation_identity()
    print('OK: federated registry resolution checks passed')


if __name__ == '__main__':
    main()
