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


def run(command, cwd):
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True)


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-cli-platform-contracts-'))
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


def assert_same_result(repo: Path, args: list[str], expect_returncode: int):
    cli_env = os.environ.copy()
    cli_env['PYTHONPATH'] = str(repo / 'src')
    cli = subprocess.run(
        [sys.executable, '-m', 'infinitas_skill.cli.main', 'compatibility', 'check-platform-contracts', *args],
        cwd=repo,
        text=True,
        capture_output=True,
        env=cli_env,
    )
    legacy = run([sys.executable, str(repo / 'scripts' / 'check-platform-contracts.py'), *args], cwd=repo)

    if cli.returncode != expect_returncode:
        fail(
            f'CLI command returned {cli.returncode}, expected {expect_returncode}\n'
            f'stdout:\n{cli.stdout}\n'
            f'stderr:\n{cli.stderr}'
        )
    if legacy.returncode != expect_returncode:
        fail(
            f'legacy command returned {legacy.returncode}, expected {expect_returncode}\n'
            f'stdout:\n{legacy.stdout}\n'
            f'stderr:\n{legacy.stderr}'
        )
    if cli.returncode != legacy.returncode:
        fail(f'CLI exit code {cli.returncode} != legacy exit code {legacy.returncode}')
    if cli.stdout != legacy.stdout:
        fail(f'CLI stdout != legacy stdout\ncli:\n{cli.stdout}\nlegacy:\n{legacy.stdout}')
    if cli.stderr != legacy.stderr:
        fail(f'CLI stderr != legacy stderr\ncli:\n{cli.stderr}\nlegacy:\n{legacy.stderr}')


def main():
    tmpdir, repo = prepare_repo()
    try:
        write_valid_docs(repo)
        assert_same_result(repo, ['--max-age-days', '30', '--stale-policy', 'fail'], expect_returncode=0)

        write_profile_contract(repo, 'codex', date='2026-03-11', urls=['https://docs.example.com/codex'])
        assert_same_result(repo, [], expect_returncode=1)
    finally:
        shutil.rmtree(tmpdir)

    print('OK: infinitas compatibility check-platform-contracts CLI mirrors legacy script output')


if __name__ == '__main__':
    main()
