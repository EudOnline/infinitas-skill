#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATHS = [
    Path('templates/basic-skill/_meta.json'),
    Path('templates/scripted-skill/_meta.json'),
    Path('templates/reference-heavy-skill/_meta.json'),
]
EXPECTED_BASELINE = 'validated 4 skill directories'


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
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-skill-meta-compat-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    return tmpdir, repo


def main():
    tmpdir, repo = prepare_repo()
    try:
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
        combined = result.stdout + result.stderr
        if EXPECTED_BASELINE not in combined:
            fail(f'unexpected baseline validation output\n{combined}')

        meta_path = repo / 'templates' / 'basic-skill' / '_meta.json'
        payload = json.loads(meta_path.read_text(encoding='utf-8'))
        payload.pop('schema_version', None)
        write_json(meta_path, payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
        combined = result.stdout + result.stderr
        if EXPECTED_BASELINE not in combined:
            fail(f'legacy schema-less _meta.json should still validate\n{combined}')

        payload = json.loads(meta_path.read_text(encoding='utf-8'))
        payload['schema_version'] = 1
        write_json(meta_path, payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
        combined = result.stdout + result.stderr
        if EXPECTED_BASELINE not in combined:
            fail(f'schema_version=1 should validate\n{combined}')

        payload['schema_version'] = 999
        write_json(meta_path, payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'schema_version' not in combined:
            fail(f'expected unsupported schema_version failure\n{combined}')

        payload['schema_version'] = 1
        write_json(meta_path, payload)

        payload.update(
            {
                'maturity': 'stable',
                'quality_score': 88,
                'capabilities': ['repo-operations', 'release-guidance'],
                'use_when': ['Need to operate inside the infinitas-skill repository'],
                'avoid_when': ['Need a general-purpose public publishing workflow'],
                'runtime_assumptions': ['Git checkout is available', 'Repository scripts may be executed'],
            }
        )
        write_json(meta_path, payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
        combined = result.stdout + result.stderr
        if EXPECTED_BASELINE not in combined:
            fail(f'valid AI decision metadata should validate\n{combined}')

        payload['use_when'] = 'Need repo operations'
        write_json(meta_path, payload)
        result = subprocess.run(
            [sys.executable, str(repo / 'scripts' / 'validate-registry.py')],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            fail('expected invalid use_when type to fail validation')
        combined = result.stdout + result.stderr
        if 'use_when' not in combined:
            fail(f'expected validation failure mentioning use_when\n{combined}')

        payload['use_when'] = ['Need to operate inside the infinitas-skill repository']
        payload['quality_score'] = 101
        write_json(meta_path, payload)
        result = subprocess.run(
            [sys.executable, str(repo / 'scripts' / 'validate-registry.py')],
            cwd=repo,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            fail('expected out-of-range quality_score to fail validation')
        combined = result.stdout + result.stderr
        if 'quality_score' not in combined:
            fail(f'expected validation failure mentioning quality_score\n{combined}')

        for rel in TEMPLATE_PATHS:
            payload = json.loads((repo / rel).read_text(encoding='utf-8'))
            if payload.get('schema_version') != 1:
                fail(f'expected template {rel} to declare schema_version=1, got {payload.get("schema_version")!r}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: skill meta schema compatibility checks passed')


if __name__ == '__main__':
    main()
