"""Repository root discovery for package-native modules."""

from __future__ import annotations

import os
from pathlib import Path


def looks_like_repo_root(path: Path) -> bool:
    return (path / "pyproject.toml").is_file() and (path / "scripts").is_dir()


def resolve_repo_root(explicit_root: str | Path | None = None) -> Path:
    if explicit_root:
        candidate = Path(explicit_root).expanduser().resolve()
        if looks_like_repo_root(candidate):
            return candidate

    for env_name in ("INFINITAS_ROOT", "INFINITAS_REPO_ROOT", "INFINITAS_BUNDLED_REPO_PATH"):
        env_root = os.environ.get(env_name)
        if not env_root:
            continue
        candidate = Path(env_root).expanduser().resolve()
        if looks_like_repo_root(candidate):
            return candidate

    module_path = Path(__file__).resolve()
    cwd = Path.cwd().resolve()
    candidates = [cwd, *cwd.parents, *module_path.parents]

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


__all__ = ["ROOT", "looks_like_repo_root", "resolve_repo_root"]
