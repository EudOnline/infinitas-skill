#!/usr/bin/env python3
import json
import os
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
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path(cwd) / 'src')
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)
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


def write_profile_contract(repo: Path, platform: str, *, date='2026-03-12', urls=None):
    urls = list(urls or ['https://example.com/source'])
    path = repo / 'profiles' / f'{platform}.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    contract = payload.get('contract') if isinstance(payload.get('contract'), dict) else {}
    contract['sources'] = urls
    contract['last_verified'] = date
    payload['contract'] = contract
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_valid_docs(repo: Path):
    for platform, title in REQUIRED_DOCS.items():
        url = f'https://docs.example.com/{platform}'
        write_contract(repo, platform, title, url=url)
        write_profile_contract(repo, platform, urls=[url])


def main():
    tmpdir, repo = prepare_repo()
    try:
        checker = [sys.executable, '-m', 'infinitas_skill.cli.main', 'compatibility', 'check-platform-contracts']

        write_valid_docs(repo)
        run([*checker, '--max-age-days', '30'], cwd=repo)

        stale_age_repo = tmpdir / 'stale-age-repo'
        shutil.copytree(repo, stale_age_repo)
        write_contract(stale_age_repo, 'claude', REQUIRED_DOCS['claude'], date='2025-01-01', url='https://docs.example.com/claude')
        write_profile_contract(stale_age_repo, 'claude', date='2025-01-01', urls=['https://docs.example.com/claude'])
        run(
            [*checker, '--max-age-days', '30'],
            cwd=stale_age_repo,
        )
        run(
            [*checker, '--max-age-days', '30', '--stale-policy', 'fail'],
            cwd=stale_age_repo,
            expect=1,
        )

        mismatch_repo = tmpdir / 'mismatch-repo'
        shutil.copytree(repo, mismatch_repo)
        write_profile_contract(mismatch_repo, 'codex', date='2026-03-11', urls=['https://docs.example.com/codex'])
        run([*checker], cwd=mismatch_repo, expect=1)

        missing_repo = tmpdir / 'missing-repo'
        shutil.copytree(repo, missing_repo)
        (missing_repo / 'docs' / 'platform-contracts' / 'codex.md').unlink()
        run([*checker], cwd=missing_repo, expect=1)

        invalid_date_repo = tmpdir / 'invalid-date-repo'
        shutil.copytree(repo, invalid_date_repo)
        write_contract(invalid_date_repo, 'claude', REQUIRED_DOCS['claude'], date='not-a-date', url='https://docs.example.com/claude')
        write_profile_contract(invalid_date_repo, 'claude', date='not-a-date', urls=['https://docs.example.com/claude'])
        run([*checker], cwd=invalid_date_repo, expect=1)

        source_repo = tmpdir / 'source-repo'
        shutil.copytree(repo, source_repo)
        write_contract(source_repo, 'openclaw', REQUIRED_DOCS['openclaw'], url='not-a-url')
        write_profile_contract(source_repo, 'openclaw', urls=['not-a-url'])
        run([*checker], cwd=source_repo, expect=1)
    finally:
        shutil.rmtree(tmpdir)

    print('OK: platform contract checks passed')


if __name__ == '__main__':
    main()
