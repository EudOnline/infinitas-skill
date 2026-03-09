#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_SLUG = 'demo-skill'
OWNER = 'import-test'
PUBLISHER = 'lvxiaoer'


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0, env=None):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-openclaw-import-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    return tmpdir, repo


def scaffold_openclaw_skill(base: Path) -> Path:
    source = base / 'openclaw-workspace' / 'skills' / FIXTURE_SLUG
    source.mkdir(parents=True, exist_ok=True)
    (source / 'SKILL.md').write_text(
        '---\n'
        f'name: {FIXTURE_SLUG}\n'
        'description: Imported fixture skill for OpenClaw bridge tests.\n'
        '---\n\n'
        '# Demo Skill\n\n'
        'Used only for OpenClaw import bridge tests.\n',
        encoding='utf-8',
    )
    (source / 'notes.txt').write_text('fixture support file\n', encoding='utf-8')
    return source


def test_confirm_mode_returns_non_mutating_plan():
    tmpdir, repo = prepare_repo()
    try:
        source_dir = scaffold_openclaw_skill(tmpdir)
        result = run(
            [
                str(repo / 'scripts' / 'import-openclaw-skill.sh'),
                str(source_dir),
                '--owner',
                OWNER,
                '--publisher',
                PUBLISHER,
                '--mode',
                'confirm',
            ],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        if payload.get('ok') is not True:
            fail(f'expected ok=true in confirm mode, got {payload!r}')
        if payload.get('state') != 'planned':
            fail(f"expected planned state, got {payload.get('state')!r}")
        target_dir = repo / 'skills' / 'incubating' / FIXTURE_SLUG
        if target_dir.exists():
            fail(f'confirm mode unexpectedly created target dir {target_dir}')
        payload_target_dir = Path(payload.get('target_dir' ) or '').resolve()
        if payload_target_dir != target_dir.resolve():
            fail(f"expected target_dir {target_dir.resolve()!s}, got {payload_target_dir!s}")
        if payload.get('qualified_name') != f'{PUBLISHER}/{FIXTURE_SLUG}':
            fail(f"unexpected qualified_name in confirm mode: {payload.get('qualified_name')!r}")
    finally:
        shutil.rmtree(tmpdir)


def test_auto_mode_copies_skill_into_incubating_and_scaffolds_registry_files():
    tmpdir, repo = prepare_repo()
    try:
        source_dir = scaffold_openclaw_skill(tmpdir)
        result = run(
            [
                str(repo / 'scripts' / 'import-openclaw-skill.sh'),
                str(source_dir),
                '--owner',
                OWNER,
                '--publisher',
                PUBLISHER,
            ],
            cwd=repo,
        )
        payload = json.loads(result.stdout)
        if payload.get('ok') is not True:
            fail(f'expected ok=true in auto mode, got {payload!r}')
        if payload.get('state') != 'imported':
            fail(f"expected imported state, got {payload.get('state')!r}")

        target_dir = repo / 'skills' / 'incubating' / FIXTURE_SLUG
        if not target_dir.is_dir():
            fail(f'missing imported target dir {target_dir}')
        if (target_dir / 'SKILL.md').read_text(encoding='utf-8') != (source_dir / 'SKILL.md').read_text(encoding='utf-8'):
            fail('expected imported SKILL.md to preserve original content')
        if (target_dir / 'notes.txt').read_text(encoding='utf-8') != 'fixture support file\n':
            fail('expected support file to be copied into imported skill')

        meta_path = target_dir / '_meta.json'
        if not meta_path.exists():
            fail('missing generated _meta.json')
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        expected_fields = {
            'name': FIXTURE_SLUG,
            'status': 'incubating',
            'owner': OWNER,
            'author': OWNER,
            'review_state': 'draft',
            'publisher': PUBLISHER,
            'qualified_name': f'{PUBLISHER}/{FIXTURE_SLUG}',
        }
        for key, expected in expected_fields.items():
            if meta.get(key) != expected:
                fail(f'expected _meta.json {key}={expected!r}, got {meta.get(key)!r}')
        if meta.get('owners') != [OWNER]:
            fail(f"expected owners to equal {[OWNER]!r}, got {meta.get('owners')!r}")
        if meta.get('summary') != 'Imported fixture skill for OpenClaw bridge tests.':
            fail(f"unexpected summary: {meta.get('summary')!r}")

        reviews_path = target_dir / 'reviews.json'
        if not reviews_path.exists():
            fail('missing generated reviews.json')
        reviews = json.loads(reviews_path.read_text(encoding='utf-8'))
        if reviews != {'version': 1, 'requests': [], 'entries': []}:
            fail(f'unexpected reviews scaffold: {reviews!r}')

        smoke_path = target_dir / 'tests' / 'smoke.md'
        if not smoke_path.exists():
            fail('missing scaffolded smoke test')
        if 'OpenClaw' not in smoke_path.read_text(encoding='utf-8'):
            fail('expected smoke test scaffold to reference OpenClaw import review')
    finally:
        shutil.rmtree(tmpdir)


def main():
    test_confirm_mode_returns_non_mutating_plan()
    test_auto_mode_copies_skill_into_incubating_and_scaffolds_registry_files()
    print('OK: openclaw import checks passed')


if __name__ == '__main__':
    main()
