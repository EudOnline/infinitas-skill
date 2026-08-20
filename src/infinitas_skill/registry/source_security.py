"""Hosted publication policy for paths likely to contain private runtime data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_SENSITIVE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".bash_history",
    ".zsh_history",
    "history.txt",
    ".git-credentials",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "auth.json",
    "cookies.json",
    "cookies.txt",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    "config.json",
    "config.yaml",
    "config.yml",
    "token.json",
}
_SENSITIVE_SUFFIXES = {".db", ".key", ".p12", ".pem", ".pfx", ".sqlite", ".sqlite3", ".crt", ".cer"}
_RUNTIME_DATA_ROOTS = {"data"}


def _normalize_allow_path(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("security.publish_allow_paths entries must be strings")
    normalized = value.strip().removeprefix("./").rstrip("/")
    path = Path(normalized)
    if (
        not normalized
        or path.is_absolute()
        or "\\" in normalized
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"invalid security.publish_allow_paths entry: {value!r}")
    return path.as_posix()


def publish_allow_paths(metadata: dict[str, Any]) -> tuple[str, ...]:
    security = metadata.get("security", {})
    if security is None:
        return ()
    if not isinstance(security, dict):
        raise ValueError("_meta.json security must be an object")
    raw = security.get("publish_allow_paths", [])
    if not isinstance(raw, list):
        raise ValueError("security.publish_allow_paths must be an array")
    return tuple(dict.fromkeys(_normalize_allow_path(item) for item in raw))


def _allowed(relative: str, allow_paths: tuple[str, ...]) -> bool:
    return any(relative == item or relative.startswith(f"{item}/") for item in allow_paths)


def sensitive_publish_paths(
    source_dir: Path,
    *,
    excluded_paths: tuple[str, ...],
    allow_paths: tuple[str, ...],
) -> tuple[str, ...]:
    blocked: list[str] = []
    for path in sorted(source_dir.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(source_dir).as_posix()
        if _allowed(relative, excluded_paths):
            continue
        relative_path = Path(relative)
        name = relative_path.name.lower()
        path_blocked = (
            relative_path.parts[0].lower() in _RUNTIME_DATA_ROOTS
            or name in _SENSITIVE_NAMES
            or relative_path.suffix.lower() in _SENSITIVE_SUFFIXES
        )
        if path_blocked and not _allowed(relative, allow_paths):
            blocked.append(relative)
    return tuple(blocked)


__all__ = ["publish_allow_paths", "sensitive_publish_paths"]
