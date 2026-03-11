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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-install-manifest-compat-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    return tmpdir, repo


def prepare_target(repo: Path) -> Path:
    target = repo / '.tmp-installed-skills'
    target.mkdir(parents=True, exist_ok=True)
    skill_dir = target / 'demo-skill'
    shutil.copytree(repo / 'templates' / 'basic-skill', skill_dir)
    meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
    meta.update(
        {
            'name': 'demo-skill',
            'version': '1.2.3',
            'status': 'active',
            'summary': 'Demo installed skill',
            'owner': 'compat-test',
            'owners': ['compat-test'],
            'author': 'compat-test',
            'review_state': 'approved',
        }
    )
    (skill_dir / 'SKILL.md').write_text(
        '---\n'
        'name: demo-skill\n'
        'description: Demo installed skill for manifest compatibility tests.\n'
        '---\n\n'
        '# Demo Skill\n',
        encoding='utf-8',
    )
    write_json(skill_dir / '_meta.json', meta)
    legacy_manifest = {
        'repo': 'https://example.invalid/repo.git',
        'updated_at': '2026-03-12T00:00:00Z',
        'skills': {
            'demo-skill': {
                'name': 'demo-skill',
                'version': '1.2.3',
                'locked_version': '1.2.3',
                'source_registry': 'self',
            }
        },
        'history': {},
    }
    write_json(target / '.infinitas-skill-install-manifest.json', legacy_manifest)
    return target


def main():
    tmpdir, repo = prepare_repo()
    try:
        target = prepare_target(repo)

        result = run([str(repo / 'scripts' / 'list-installed.sh'), str(target)], cwd=repo)
        combined = result.stdout + result.stderr
        if '- demo-skill: 1.2.3' not in combined:
            fail(f'legacy manifest should be accepted by list-installed\n{combined}')

        result = run(
            [
                sys.executable,
                str(repo / 'scripts' / 'resolve-install-plan.py'),
                '--skill-dir',
                str(repo / 'templates' / 'basic-skill'),
                '--target-dir',
                str(target),
                '--json',
            ],
            cwd=repo,
        )
        plan = json.loads(result.stdout)
        if not isinstance(plan.get('steps'), list):
            fail(f'expected dependency planner to accept legacy manifest\n{result.stdout}\n{result.stderr}')

        manifest_path = target / '.infinitas-skill-install-manifest.json'
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))
        payload['schema_version'] = 999
        write_json(manifest_path, payload)
        result = run([str(repo / 'scripts' / 'list-installed.sh'), str(target)], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'schema_version' not in combined:
            fail(f'expected unsupported schema_version error\n{combined}')

        payload['schema_version'] = 1
        write_json(manifest_path, payload)
        result = run([str(repo / 'scripts' / 'update-install-manifest.py'), str(target), str(target / 'demo-skill'), str(target / 'demo-skill'), 'sync', '1.2.3', json.dumps({'registry_name': 'self'})], cwd=repo)
        combined = result.stdout + result.stderr
        if 'updated manifest:' not in combined:
            fail(f'expected manifest rewrite to succeed\n{combined}')
        payload = json.loads(manifest_path.read_text(encoding='utf-8'))
        if payload.get('schema_version') != 1:
            fail(f"expected rewritten manifest to declare schema_version=1, got {payload.get('schema_version')!r}")
    finally:
        shutil.rmtree(tmpdir)

    print('OK: install manifest compatibility checks passed')


if __name__ == '__main__':
    main()
