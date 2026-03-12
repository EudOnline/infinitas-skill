#!/usr/bin/env python3
import importlib.util
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


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-canonical-skill-compat-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location('canonical_skill_lib', path)
    if spec is None or spec.loader is None:
        fail(f'unable to load module from {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scaffold_canonical_skill(repo: Path):
    skill_dir = repo / 'skills-src' / 'demo-skill'
    write_json(
        skill_dir / 'skill.json',
        {
            'schema_version': 1,
            'name': 'demo-skill',
            'summary': 'Canonical demo skill',
            'description': 'Use when checking canonical source loading.',
            'triggers': ['when validating canonical skills'],
            'examples': ['validate the canonical demo skill'],
            'instructions_body': 'instructions.md',
            'tool_intents': {
                'required': ['file_read'],
                'optional': ['plan_tracking'],
            },
            'degrades_to': {
                'no_subagent_dispatch': 'sequential'
            },
            'distribution': {
                'public_publish_allowed': False,
                'text_only_required': True,
            },
            'verification': {
                'required_platforms': ['codex', 'openclaw'],
                'smoke_prompts': ['prompts/default.txt'],
            },
        },
    )
    (skill_dir / 'instructions.md').write_text(
        '# Demo Skill\n\nCanonical instructions body.\n',
        encoding='utf-8',
    )
    write_json(skill_dir / 'platforms' / 'codex.json', {'emit_agents_md_snippet': True})
    return skill_dir


def main():
    tmpdir, repo = prepare_repo()
    try:
        canonical_dir = scaffold_canonical_skill(repo)
        module = load_module(repo / 'scripts' / 'canonical_skill_lib.py')

        canonical = module.load_skill_source(canonical_dir)
        if canonical.get('name') != 'demo-skill':
            fail(f"expected canonical name 'demo-skill', got {canonical.get('name')!r}")
        if canonical.get('source_mode') != 'canonical':
            fail(f"expected source_mode 'canonical', got {canonical.get('source_mode')!r}")
        body_path = Path(canonical.get('instructions_body_path') or '')
        if body_path.name != 'instructions.md':
            fail(f'expected canonical instructions body path to end with instructions.md, got {body_path!r}')

        legacy = module.load_skill_source(repo / 'templates' / 'basic-skill')
        if legacy.get('name') != 'basic-skill':
            fail(f"expected legacy name 'basic-skill', got {legacy.get('name')!r}")
        if legacy.get('source_mode') != 'legacy':
            fail(f"expected source_mode 'legacy', got {legacy.get('source_mode')!r}")
        legacy_path = Path(legacy.get('instructions_body_path') or '')
        if legacy_path.name != 'SKILL.md':
            fail(f'expected legacy instructions body path to end with SKILL.md, got {legacy_path!r}')

        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py'), 'skills-src/demo-skill'], cwd=repo)
        combined = result.stdout + result.stderr
        if 'validated 1 skill directories' not in combined and 'validated 1 canonical skill sources' not in combined:
            fail(f'unexpected canonical validation output\n{combined}')

        run([str(repo / 'scripts' / 'check-skill.sh'), str(canonical_dir)], cwd=repo)

        payload = json.loads((canonical_dir / 'skill.json').read_text(encoding='utf-8'))
        payload['schema_version'] = 999
        write_json(canonical_dir / 'skill.json', payload)
        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py'), 'skills-src/demo-skill'], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'schema_version' not in combined:
            fail(f'expected canonical schema version failure\n{combined}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: canonical skill loader checks passed')


if __name__ == '__main__':
    main()
