from __future__ import annotations

import errno
import fcntl
import json
import os
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class RepoOpError(Exception):
    pass


class LockTimeout(RepoOpError):
    pass


def _safe_relative_path(value: str) -> Path:
    rel = Path(value)
    if rel.is_absolute():
        raise RepoOpError(f"path must be relative: {value}")
    if ".." in rel.parts:
        raise RepoOpError(f"path must stay within the skill directory: {value}")
    return rel


@contextmanager
def locked_repo(lock_path: Path, *, timeout_seconds: float = 120) -> Iterator[None]:
    """Acquire an exclusive file lock on *lock_path* with a timeout.

    Parameters
    ----------
    lock_path:
        Path to the lock file (will be created if missing).
    timeout_seconds:
        Maximum seconds to wait for the lock. Raises :class:`LockTimeout`
        if the deadline is exceeded.
    """
    lock_path = Path(lock_path).resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    with lock_path.open("a+", encoding="utf-8") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES):
                    raise
                if time.monotonic() >= deadline:
                    raise LockTimeout(
                        f"could not acquire repo lock {lock_path} within {timeout_seconds}s"
                    ) from exc
                time.sleep(0.5)
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
    rendered = f"$ {' '.join(command)}"
    if combined:
        rendered += f"\n{combined}"
    if result.returncode != 0:
        raise RepoOpError(rendered or f"command failed: {command!r}")
    return rendered


def current_branch(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RepoOpError(result.stderr.strip() or "could not resolve current branch")
    return result.stdout.strip() or "main"


def _normalize_file_content(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    return str(value)
