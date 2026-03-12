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
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-render-skill-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def scaffold_canonical_skill(repo: Path):
    skill_dir = repo / 'skills-src' / 'render-demo'
    write_json(
        skill_dir / 'skill.json',
        {
            'schema_version': 1,
            'name': 'render-demo',
            'summary': 'Renderer demo skill',
            'description': 'Use when validating rendered skill outputs.',
            'triggers': ['when rendering skills'],
            'examples': ['render the demo skill'],
            'instructions_body': 'instructions.md',
            'tool_intents': {
                'required': ['file_read', 'plan_tracking'],
                'optional': ['subagent_dispatch'],
            },
            'distribution': {
                'public_publish_allowed': True,
                'text_only_required': True,
            },
            'verification': {
                'required_platforms': ['claude', 'codex', 'openclaw'],
                'smoke_prompts': ['prompts/default.txt'],
            },
        },
    )
    (skill_dir / 'instructions.md').write_text('# Render Demo\n\nShared instructions body.\n', encoding='utf-8')
    (skill_dir / 'references').mkdir(parents=True, exist_ok=True)
    (skill_dir / 'references' / 'notes.md').write_text('Renderer support note.\n', encoding='utf-8')
    write_json(skill_dir / 'platforms' / 'openclaw.json', {'requires': ['shell', 'git']})
    return skill_dir


def assert_skill_markdown(path: Path, expected_fragments):
    if not path.is_file():
        fail(f'missing rendered SKILL.md: {path}')
    text = path.read_text(encoding='utf-8')
    for fragment in expected_fragments:
        if fragment not in text:
            fail(f'expected rendered SKILL.md to contain {fragment!r}\n{text}')


def main():
    tmpdir, repo = prepare_repo()
    try:
        skill_dir = scaffold_canonical_skill(repo)
        out_root = repo / 'build'
        cases = {
            'codex': ['name: render-demo', 'description: Use when validating rendered skill outputs.'],
            'claude': ['name: render-demo', 'description: Use when validating rendered skill outputs.'],
            'openclaw': ['name: render-demo', 'description: Use when validating rendered skill outputs.', 'metadata.openclaw.requires: shell, git'],
        }
        for platform, fragments in cases.items():
            out_dir = out_root / platform / 'render-demo'
            result = run(
                [sys.executable, str(repo / 'scripts' / 'render-skill.py'), '--skill-dir', str(skill_dir), '--platform', platform, '--out', str(out_dir)],
                cwd=repo,
            )
            payload = json.loads(result.stdout)
            if payload.get('platform') != platform:
                fail(f'expected payload platform {platform!r}, got {payload.get("platform")!r}')
            assert_skill_markdown(out_dir / 'SKILL.md', fragments)
            if not (out_dir / 'references' / 'notes.md').is_file():
                fail(f'expected renderer to copy references/notes.md for {platform}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: render-skill checks passed')


if __name__ == '__main__':
    main()
