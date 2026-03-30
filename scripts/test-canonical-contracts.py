#!/usr/bin/env python3
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = {
    'claude': 'Claude Platform Contract',
    'codex': 'Codex Platform Contract',
    'openclaw': 'OpenClaw Platform Contract',
}
PROFILE_PATHS = [
    Path('profiles/claude.json'),
    Path('profiles/codex.json'),
    Path('profiles/openclaw.json'),
]


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


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-canonical-contracts-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def load_json(path: Path):
    if not path.exists():
        fail(f'missing expected file: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def assert_contains(text: str, pattern: str, label: str):
    if pattern not in text:
        fail(f'missing {label!r}: expected to find {pattern!r}')


def main():
    tmpdir, repo = prepare_repo()
    try:
        sys.path.insert(0, str(repo / 'scripts'))
        from platform_contract_lib import validate_platform_contract

        schema = load_json(repo / 'schemas' / 'skill-canonical.schema.json')
        if schema.get('$schema') != 'https://json-schema.org/draft/2020-12/schema':
            fail(f'unexpected skill canonical schema header: {schema.get("$schema")!r}')
        properties = schema.get('properties') or {}
        if 'tool_intents' not in properties:
            fail('expected skill canonical schema to define tool_intents')
        required = schema.get('required') or []
        for field in ['schema_version', 'name', 'summary', 'description', 'instructions_body', 'tool_intents', 'verification']:
            if field not in required:
                fail(f'expected skill canonical schema required fields to include {field!r}')

        profile_schema = load_json(repo / 'schemas' / 'platform-profile.schema.json')
        if profile_schema.get('$schema') != 'https://json-schema.org/draft/2020-12/schema':
            fail(f'unexpected platform profile schema header: {profile_schema.get("$schema")!r}')

        expected_platforms = {'claude', 'codex', 'openclaw'}
        seen_platforms = set()
        for rel in PROFILE_PATHS:
            payload = load_json(repo / rel)
            platform = payload.get('platform')
            seen_platforms.add(platform)
            if payload.get('schema_version') != 1:
                fail(f'expected {rel} schema_version=1, got {payload.get("schema_version")!r}')
            runtime = payload.get('runtime') or {}
            skill_dirs = runtime.get('skill_dir_candidates') or []
            if not skill_dirs:
                fail(f'expected {rel} to define runtime.skill_dir_candidates')
            if runtime.get('entrypoint') != 'SKILL.md':
                fail(f'expected {rel} runtime.entrypoint to equal SKILL.md, got {runtime.get("entrypoint")!r}')
            contract = payload.get('contract') or {}
            sources = contract.get('sources') or []
            if not sources or not all(isinstance(url, str) and url.startswith('https://') for url in sources):
                fail(f'expected {rel} to define HTTPS contract sources, got {sources!r}')
            if not contract.get('last_verified'):
                fail(f'expected {rel} to define contract.last_verified')
            doc_payload, doc_errors = validate_platform_contract(repo / 'docs' / 'platform-contracts' / f'{platform}.md', REQUIRED_DOCS[platform])
            if doc_errors:
                fail(f'expected {platform} contract doc to validate, got {doc_errors!r}')
            if sources != doc_payload.get('official_sources'):
                fail(f'expected {rel} contract.sources to match docs/platform-contracts/{platform}.md, got {sources!r}')
            expected_last_verified = doc_payload.get('last_verified').isoformat() if doc_payload.get('last_verified') else None
            if contract.get('last_verified') != expected_last_verified:
                fail(
                    f"expected {rel} contract.last_verified {contract.get('last_verified')!r} "
                    f"to match docs/platform-contracts/{platform}.md {expected_last_verified!r}"
                )
        if seen_platforms != expected_platforms:
            fail(f'expected profile platforms {expected_platforms!r}, got {seen_platforms!r}')

        readme = (repo / 'README.md').read_text(encoding='utf-8')
        matrix = (repo / 'docs' / 'reference' / 'compatibility-matrix.md').read_text(encoding='utf-8')
        contract_doc = (repo / 'docs' / 'reference' / 'compatibility-contract.md').read_text(encoding='utf-8')
        assert_contains(readme, 'declared support', 'README declared support terminology')
        assert_contains(readme, 'verified support', 'README verified support terminology')
        assert_contains(matrix, 'declared support', 'compatibility matrix declared support terminology')
        assert_contains(matrix, 'verified support', 'compatibility matrix verified support terminology')
        assert_contains(contract_doc, 'declared support', 'compatibility contract declared support terminology')
        assert_contains(contract_doc, 'verified support', 'compatibility contract verified support terminology')

        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
        combined = result.stdout + result.stderr
        if not re.search(r'validated\s+\d+\s+skill directories', combined):
            fail(f'unexpected validation output\n{combined}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: canonical contracts checks passed')


if __name__ == '__main__':
    main()
