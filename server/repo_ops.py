from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path


class RepoOpError(Exception):
    pass


def _safe_relative_path(value: str) -> Path:
    rel = Path(value)
    if rel.is_absolute():
        raise RepoOpError(f'path must be relative: {value}')
    if '..' in rel.parts:
        raise RepoOpError(f'path must stay within the skill directory: {value}')
    return rel


@contextmanager
def locked_repo(lock_path: Path):
    lock_path = Path(lock_path).resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+', encoding='utf-8') as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run_command(repo_path: Path, command: list[str], *, env: dict | None = None) -> str:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    result = subprocess.run(
        command,
        cwd=repo_path,
        text=True,
        capture_output=True,
        env=full_env,
    )
    combined = "\n".join(
        part for part in [result.stdout.strip(), result.stderr.strip()] if part
    ).strip()
    rendered = f'$ {" ".join(command)}'
    if combined:
        rendered += f'\n{combined}'
    if result.returncode != 0:
        raise RepoOpError(rendered or f'command failed: {command!r}')
    return rendered


def git_status_is_clean(repo_path: Path) -> bool:
    result = subprocess.run(
        ['git', 'status', '--short'],
        cwd=repo_path,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RepoOpError(result.stderr.strip() or 'git status failed')
    return not result.stdout.strip()


def current_branch(repo_path: Path) -> str:
    result = subprocess.run(
        ['git', 'branch', '--show-current'],
        cwd=repo_path,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RepoOpError(result.stderr.strip() or 'could not resolve current branch')
    return result.stdout.strip() or 'main'


def commit_and_push(repo_path: Path, *, message: str) -> list[str]:
    logs: list[str] = []
    if git_status_is_clean(repo_path):
        return logs
    logs.append(run_command(repo_path, ['git', 'add', '.']))
    logs.append(run_command(repo_path, ['git', 'commit', '-m', message]))
    logs.append(run_command(repo_path, ['git', 'push', 'origin', current_branch(repo_path)]))
    return logs


def _normalize_file_content(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    return str(value)


def materialize_submission_skill(
    repo_path: Path,
    *,
    skill_name: str,
    payload: dict,
    review_payload: dict | None = None,
) -> Path:
    files = payload.get('files')
    if not isinstance(files, dict) or not files:
        raise RepoOpError('submission payload must contain a non-empty files object')

    skill_dir = repo_path / 'skills' / 'incubating' / skill_name
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    skill_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, content in files.items():
        if not isinstance(rel_path, str) or not rel_path.strip():
            raise RepoOpError('submission payload file keys must be non-empty strings')
        target = skill_dir / _safe_relative_path(rel_path.strip())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_normalize_file_content(content), encoding='utf-8')

    meta_path = skill_dir / '_meta.json'
    if not meta_path.exists():
        raise RepoOpError('submission payload must provide _meta.json')
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta['name'] = meta.get('name') or skill_name
    meta['status'] = 'incubating'
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    if review_payload is not None:
        (skill_dir / 'reviews.json').write_text(
            json.dumps(review_payload, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )

    return skill_dir
