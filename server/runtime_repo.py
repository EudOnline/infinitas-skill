from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from server.repo_ops import RepoOpError, locked_repo

BOOTSTRAP_IGNORE = shutil.ignore_patterns(
    '.git',
    '.DS_Store',
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    '.coverage',
    '.coverage.*',
    'htmlcov',
    '.venv',
    '.state',
    '.deploy',
    'node_modules',
)


class RuntimeRepoError(RepoOpError):
    pass


@dataclass(frozen=True)
class RuntimeRepoBootstrapResult:
    seeded: bool
    repo_path: Path
    branch: str
    origin_configured: bool


def _run_git(repo_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['git', *args], cwd=repo_path, text=True, capture_output=True)


def _ensure_success(result: subprocess.CompletedProcess[str], action: str):
    if result.returncode == 0:
        return
    message = result.stderr.strip() or result.stdout.strip() or f'{action} failed'
    raise RuntimeRepoError(message)


def is_git_repo(path: Path) -> bool:
    path = Path(path).resolve()
    if not path.is_dir():
        return False
    result = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], cwd=path, text=True, capture_output=True)
    return result.returncode == 0 and result.stdout.strip() == 'true'


def _copy_snapshot(source: Path, target: Path):
    for child in target.iterdir():
        if child.name == '.git':
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    for child in source.iterdir():
        if child.name == '.git':
            continue
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(child, destination, ignore=BOOTSTRAP_IGNORE, symlinks=True)
        else:
            shutil.copy2(child, destination)


def _configure_origin(repo_path: Path, origin_url: str) -> bool:
    origin_url = str(origin_url or '').strip()
    if not origin_url:
        return False

    result = _run_git(repo_path, 'remote', 'get-url', 'origin')
    if result.returncode == 0:
        current = result.stdout.strip()
        if current == origin_url:
            return False
        _ensure_success(_run_git(repo_path, 'remote', 'set-url', 'origin', origin_url), 'git remote set-url origin')
        return True

    _ensure_success(_run_git(repo_path, 'remote', 'add', 'origin', origin_url), 'git remote add origin')
    return True


def ensure_runtime_repo(
    *,
    bundled_repo_path: Path,
    repo_path: Path,
    repo_lock_path: Path,
    branch: str = 'main',
    origin_url: str = '',
    git_user_name: str = 'Infinitas Hosted Registry',
    git_user_email: str = 'hosted-registry@example.com',
    allow_reset: bool = False,
) -> RuntimeRepoBootstrapResult:
    bundled_repo_path = Path(bundled_repo_path).expanduser().resolve()
    repo_path = Path(repo_path).expanduser().resolve()
    repo_lock_path = Path(repo_lock_path).expanduser().resolve()
    branch = str(branch or 'main').strip() or 'main'

    if not bundled_repo_path.is_dir():
        raise RuntimeRepoError(f'bundled repo path does not exist: {bundled_repo_path}')

    repo_path.parent.mkdir(parents=True, exist_ok=True)
    repo_lock_path.parent.mkdir(parents=True, exist_ok=True)

    with locked_repo(repo_lock_path):
        if is_git_repo(repo_path):
            origin_configured = _configure_origin(repo_path, origin_url)
            return RuntimeRepoBootstrapResult(
                seeded=False,
                repo_path=repo_path,
                branch=branch,
                origin_configured=origin_configured,
            )

        if repo_path.exists():
            existing = list(repo_path.iterdir())
            if existing and not allow_reset:
                raise RuntimeRepoError(
                    f'repo path exists but is not a git worktree: {repo_path}. '
                    'Clear it first or set INFINITAS_SERVER_REPO_BOOTSTRAP_RESET=1.'
                )
            if not repo_path.is_dir():
                raise RuntimeRepoError(f'repo path is not a directory: {repo_path}')
        else:
            repo_path.mkdir(parents=True, exist_ok=True)

        _copy_snapshot(bundled_repo_path, repo_path)

        _ensure_success(_run_git(repo_path, 'init', '-b', branch), f'git init {branch}')
        _ensure_success(_run_git(repo_path, 'config', 'user.name', git_user_name), 'git config user.name')
        _ensure_success(_run_git(repo_path, 'config', 'user.email', git_user_email), 'git config user.email')
        _ensure_success(_run_git(repo_path, 'add', '.'), 'git add .')
        _ensure_success(
            _run_git(repo_path, 'commit', '-m', 'bootstrap: seed hosted runtime repo from image snapshot'),
            'git commit bootstrap snapshot',
        )
        origin_configured = _configure_origin(repo_path, origin_url)

        return RuntimeRepoBootstrapResult(
            seeded=True,
            repo_path=repo_path,
            branch=branch,
            origin_configured=origin_configured,
        )
