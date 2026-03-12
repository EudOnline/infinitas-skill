#!/usr/bin/env python3
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
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-platform-contracts-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__', '.worktrees'),
    )
    return tmpdir, repo


def write_contract(repo: Path, platform: str, title: str, *, date='2026-03-12', url='https://example.com/source'):
    path = repo / 'docs' / 'platform-contracts' / f'{platform}.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '\n'.join(
            [
                f'# {title}',
                '## Stable assumptions',
                '- Stable item',
                '## Volatile assumptions',
                '- Volatile item',
                '## Official sources',
                f'- {url}',
                '## Last verified',
                date,
                '## Verification steps',
                '- Re-check upstream docs',
                '## Known gaps',
                '- Pending upstream clarifications',
                '',
            ]
        ),
        encoding='utf-8',
    )


def write_valid_docs(repo: Path):
    for platform, title in REQUIRED_DOCS.items():
        write_contract(repo, platform, title, url=f'https://docs.example.com/{platform}')


def main():
    tmpdir, repo = prepare_repo()
    try:
        checker = repo / 'scripts' / 'check-platform-contracts.py'

        write_valid_docs(repo)
        run([sys.executable, str(checker), '--max-age-days', '30'], cwd=repo)

        missing_repo = tmpdir / 'missing-repo'
        shutil.copytree(repo, missing_repo)
        (missing_repo / 'docs' / 'platform-contracts' / 'codex.md').unlink()
        run([sys.executable, str(missing_repo / 'scripts' / 'check-platform-contracts.py')], cwd=missing_repo, expect=1)

        stale_repo = tmpdir / 'stale-repo'
        shutil.copytree(repo, stale_repo)
        write_contract(stale_repo, 'claude', REQUIRED_DOCS['claude'], date='not-a-date', url='https://docs.example.com/claude')
        run([sys.executable, str(stale_repo / 'scripts' / 'check-platform-contracts.py')], cwd=stale_repo, expect=1)

        source_repo = tmpdir / 'source-repo'
        shutil.copytree(repo, source_repo)
        write_contract(source_repo, 'openclaw', REQUIRED_DOCS['openclaw'], url='not-a-url')
        run([sys.executable, str(source_repo / 'scripts' / 'check-platform-contracts.py')], cwd=source_repo, expect=1)
    finally:
        shutil.rmtree(tmpdir)

    print('OK: platform contract checks passed')


if __name__ == '__main__':
    main()
