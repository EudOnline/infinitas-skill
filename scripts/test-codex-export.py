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


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-codex-export-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def scaffold_skill(repo: Path):
    skill_dir = repo / 'skills-src' / 'codex-demo'
    write_json(
        skill_dir / 'skill.json',
        {
            'schema_version': 1,
            'name': 'codex-demo',
            'summary': 'Codex demo skill',
            'description': 'Use when validating Codex exports.',
            'instructions_body': 'instructions.md',
            'tool_intents': {
                'required': ['file_read', 'plan_tracking'],
                'optional': ['subagent_dispatch'],
            },
            'verification': {
                'required_platforms': ['codex'],
            },
        },
    )
    (skill_dir / 'instructions.md').write_text('# Codex Demo\n\nCodex renderer demo.\n', encoding='utf-8')
    write_json(
        skill_dir / 'platforms' / 'codex.json',
        {
            'emit_openai_yaml': True,
            'emit_agents_md_snippet': True,
        },
    )
    return skill_dir


def main():
    tmpdir, repo = prepare_repo()
    try:
        skill_dir = scaffold_skill(repo)
        out_dir = repo / 'build' / 'codex' / 'codex-demo'
        result = run([str(repo / 'scripts' / 'export-codex-skill.sh'), '--skill-dir', str(skill_dir), '--out', str(out_dir)], cwd=repo)
        payload = json.loads(result.stdout)
        if payload.get('platform') != 'codex':
            fail(f"expected platform 'codex', got {payload.get('platform')!r}")
        if not (out_dir / 'SKILL.md').is_file():
            fail('missing rendered Codex SKILL.md')
        skill_md = (out_dir / 'SKILL.md').read_text(encoding='utf-8')
        if 'name: codex-demo' not in skill_md:
            fail(f'expected Codex SKILL.md to contain frontmatter name\n{skill_md}')
        if not (out_dir / 'agents' / 'openai.yaml').is_file():
            fail('expected export to emit agents/openai.yaml')
        if not (out_dir / 'AGENTS.md').is_file():
            fail('expected export to emit AGENTS.md snippet file')

        run([sys.executable, str(repo / 'scripts' / 'check-codex-compat.py'), '--skill-dir', str(out_dir)], cwd=repo)
    finally:
        shutil.rmtree(tmpdir)

    print('OK: codex export checks passed')


if __name__ == '__main__':
    main()
