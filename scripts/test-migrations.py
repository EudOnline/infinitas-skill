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
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-migrations-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    return tmpdir, repo


def prepare_legacy_inputs(repo: Path):
    meta_path = repo / 'templates' / 'basic-skill' / '_meta.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta.pop('schema_version', None)
    write_json(meta_path, meta)

    target = repo / '.tmp-migration-target'
    target.mkdir(parents=True, exist_ok=True)
    manifest = {
        'repo': 'https://example.invalid/repo.git',
        'updated_at': '2026-03-12T00:00:00Z',
        'skills': {'demo-skill': {'name': 'demo-skill', 'version': '1.2.3'}},
        'history': {},
    }
    write_json(target / '.infinitas-skill-install-manifest.json', manifest)
    return meta_path, target


def main():
    tmpdir, repo = prepare_repo()
    try:
        meta_path, target = prepare_legacy_inputs(repo)

        result = run([sys.executable, str(repo / 'scripts' / 'migrate-skill-meta.py'), '--check', str(meta_path)], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'would update schema_version to 1' not in combined:
            fail(f'expected skill-meta migration check output\n{combined}')

        result = run([sys.executable, str(repo / 'scripts' / 'migrate-install-manifest.py'), '--check', str(target)], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'would write schema_version' not in combined:
            fail(f'expected install-manifest migration check output\n{combined}')

        run([sys.executable, str(repo / 'scripts' / 'migrate-skill-meta.py'), str(meta_path)], cwd=repo)
        run([sys.executable, str(repo / 'scripts' / 'migrate-install-manifest.py'), str(target)], cwd=repo)

        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('schema_version') != 1:
            fail(f"expected migrated skill meta to have schema_version=1, got {meta.get('schema_version')!r}")

        manifest = json.loads((target / '.infinitas-skill-install-manifest.json').read_text(encoding='utf-8'))
        if manifest.get('schema_version') != 1:
            fail(f"expected migrated install manifest to have schema_version=1, got {manifest.get('schema_version')!r}")

        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
        combined = result.stdout + result.stderr
        if 'validated 3 skill directories' not in combined:
            fail(f'expected migrated repo to validate\n{combined}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: migration command checks passed')


if __name__ == '__main__':
    main()
