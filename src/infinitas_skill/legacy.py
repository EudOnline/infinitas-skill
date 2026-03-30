"""Temporary bridge helpers for modules that still live under scripts/."""

from importlib import import_module
import os
import sys
from pathlib import Path


def looks_like_repo_root(path: Path) -> bool:
    return (path / 'pyproject.toml').is_file() and (path / 'scripts').is_dir()


def resolve_repo_root(explicit_root: str | Path | None = None) -> Path:
    if explicit_root:
        candidate = Path(explicit_root).expanduser().resolve()
        if looks_like_repo_root(candidate):
            return candidate

    env_root = os.environ.get('INFINITAS_ROOT') or os.environ.get('INFINITAS_REPO_ROOT')
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if looks_like_repo_root(candidate):
            return candidate

    module_path = Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    candidates = [*module_path.parents, cwd, *cwd.parents]

    seen = set()
    for candidate in candidates:
        resolved = Path(candidate).resolve()
        marker = str(resolved)
        if marker in seen:
            continue
        seen.add(marker)
        if looks_like_repo_root(resolved):
            return resolved

    if len(module_path.parents) > 2:
        return module_path.parents[2]
    return module_path.parent


ROOT = resolve_repo_root()


def ensure_legacy_scripts_on_path(root: str | Path | None = None) -> Path:
    repo_root = Path(root).resolve() if root else ROOT
    scripts_dir = repo_root / 'scripts'
    if scripts_dir.is_dir():
        scripts_path = str(scripts_dir)
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
    return scripts_dir


def import_legacy_module(name: str, *, root: str | Path | None = None):
    ensure_legacy_scripts_on_path(root)
    return import_module(name)


__all__ = [
    'ROOT',
    'ensure_legacy_scripts_on_path',
    'import_legacy_module',
    'looks_like_repo_root',
    'resolve_repo_root',
]
