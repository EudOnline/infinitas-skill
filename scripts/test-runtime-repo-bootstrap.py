#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from server.runtime_repo import ensure_runtime_repo, is_git_repo


def fail(message: str):
    print(f'FAIL: {message}')
    raise SystemExit(1)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(['git', *args], cwd=repo, text=True, capture_output=True)
    if result.returncode != 0:
        fail(f'git {" ".join(args)} failed in {repo}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}')
    return result.stdout.strip()


def scenario_bootstrap_empty_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-runtime-repo-test-'))
    try:
        bundle = tmpdir / 'bundle'
        repo = tmpdir / 'repo'
        lock = tmpdir / 'state' / 'repo.lock'
        bundle.mkdir()
        (bundle / 'README.md').write_text('# bundled snapshot\n', encoding='utf-8')
        (bundle / 'scripts').mkdir()
        (bundle / 'scripts' / 'hello.sh').write_text('#!/usr/bin/env bash\necho hello\n', encoding='utf-8')

        result = ensure_runtime_repo(
            bundled_repo_path=bundle,
            repo_path=repo,
            repo_lock_path=lock,
            branch='main',
            origin_url='git@example.com:org/infinitas-skill.git',
            git_user_name='Bootstrap Bot',
            git_user_email='bootstrap@example.com',
        )

        if not result.seeded:
            fail('expected first bootstrap to seed the runtime repo')
        if not is_git_repo(repo):
            fail(f'expected git repo at {repo}')
        if not (repo / 'README.md').exists():
            fail('expected snapshot files to be copied into runtime repo')
        if run_git(repo, 'branch', '--show-current') != 'main':
            fail('expected bootstrapped repo to be on main')
        if run_git(repo, 'remote', 'get-url', 'origin') != 'git@example.com:org/infinitas-skill.git':
            fail('expected bootstrap to configure origin')
        if 'bootstrap: seed hosted runtime repo from image snapshot' not in run_git(repo, 'log', '-1', '--pretty=%s'):
            fail('expected bootstrap commit to be present')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_existing_repo_is_reused():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-runtime-repo-test-'))
    try:
        bundle = tmpdir / 'bundle'
        repo = tmpdir / 'repo'
        lock = tmpdir / 'state' / 'repo.lock'
        bare = tmpdir / 'origin.git'
        bundle.mkdir()
        (bundle / 'README.md').write_text('# bundled snapshot\n', encoding='utf-8')
        repo.mkdir()
        subprocess.run(['git', 'init', '--bare', str(bare)], cwd=tmpdir, text=True, capture_output=True, check=True)
        run_git(repo, 'init', '-b', 'main')
        run_git(repo, 'config', 'user.name', 'Existing Repo')
        run_git(repo, 'config', 'user.email', 'existing@example.com')
        (repo / 'KEEP.txt').write_text('keep me\n', encoding='utf-8')
        run_git(repo, 'add', '.')
        run_git(repo, 'commit', '-m', 'existing commit')

        result = ensure_runtime_repo(
            bundled_repo_path=bundle,
            repo_path=repo,
            repo_lock_path=lock,
            branch='main',
            origin_url='git@example.com:org/infinitas-skill.git',
        )

        if result.seeded:
            fail('expected existing git repo to be reused without reseeding')
        if not (repo / 'KEEP.txt').exists():
            fail('expected existing repo contents to stay in place')
        if run_git(repo, 'remote', 'get-url', 'origin') != 'git@example.com:org/infinitas-skill.git':
            fail('expected origin to be added to an existing repo')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    scenario_bootstrap_empty_repo()
    scenario_existing_repo_is_reused()
    print('OK: runtime repo bootstrap checks passed')


if __name__ == '__main__':
    main()
