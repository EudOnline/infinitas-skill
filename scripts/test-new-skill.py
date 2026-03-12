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


def main():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-new-skill-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    try:
        run([str(repo / 'scripts' / 'new-skill.sh'), 'lvxiaoer/demo-skill', 'basic'], cwd=repo)
        skill_dir = repo / 'skills' / 'incubating' / 'demo-skill'
        if not skill_dir.is_dir():
            fail(f'missing scaffolded skill directory: {skill_dir}')

        skill_md = (skill_dir / 'SKILL.md').read_text(encoding='utf-8')
        if 'name: demo-skill' not in skill_md:
            fail(f'expected scaffolded SKILL.md name to be updated\n{skill_md}')

        meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
        if meta.get('name') != 'demo-skill':
            fail(f"expected scaffolded name 'demo-skill', got {meta.get('name')!r}")
        if meta.get('publisher') != 'lvxiaoer':
            fail(f"expected scaffolded publisher 'lvxiaoer', got {meta.get('publisher')!r}")
        if meta.get('qualified_name') != 'lvxiaoer/demo-skill':
            fail(f"unexpected qualified_name: {meta.get('qualified_name')!r}")
    finally:
        shutil.rmtree(tmpdir)

    print('OK: new-skill scaffolding checks passed')


if __name__ == '__main__':
    main()
