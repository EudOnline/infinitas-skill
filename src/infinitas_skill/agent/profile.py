from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path
from typing import Any


def config_root() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME")
    root = Path(raw).expanduser() if raw else Path.home() / ".config"
    return root / "infinitas"


def profile_path(name: str) -> Path:
    normalized = str(name or "default").strip()
    if not normalized or normalized in {".", ".."} or "/" in normalized or "\\" in normalized:
        raise ValueError("invalid Agent profile name")
    return config_root() / "agents" / f"{normalized}.json"


def pending_rotation_path(name: str) -> Path:
    path = profile_path(name)
    return path.with_name(f".{path.name}.pending-rotation")


def verifier(raw: str) -> str:
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint(api_verifier: str) -> str:
    return hashlib.sha256(
        f"infinitas-agent-fingerprint-v1\0{api_verifier}".encode("utf-8")
    ).hexdigest()[:16]


def _reject_profile_symlinks(path: Path) -> None:
    root = config_root()
    for candidate in (root, path.parent, path):
        if candidate.is_symlink():
            raise ValueError(f"Agent profile path must not be a symlink: {candidate}")


def _preserve_existing_credentials(path: Path, payload: dict[str, Any]) -> None:
    if not path.exists():
        return
    existing = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(existing, dict):
        raise ValueError("existing Agent profile must contain an object")
    for field in ("api_key", "status_key"):
        current = existing.get(field)
        replacement = payload.get(field)
        if current and replacement != current:
            raise ValueError(f"refusing to replace existing Agent profile {field}")


def _write_profile_path(path: Path, payload: dict[str, Any], *, preserve_credentials: bool) -> Path:
    _reject_profile_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_profile_symlinks(path)
    path.parent.chmod(0o700)
    if preserve_credentials:
        _preserve_existing_credentials(path, payload)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        path.chmod(0o600)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        temp_path.unlink(missing_ok=True)
    return path


def write_profile(name: str, payload: dict[str, Any]) -> Path:
    return _write_profile_path(profile_path(name), payload, preserve_credentials=True)


def replace_profile_credentials(
    name: str, payload: dict[str, Any], *, expected_api_key: str
) -> Path:
    path = profile_path(name)
    existing = read_profile(name)
    if existing.get("api_key") != expected_api_key:
        raise ValueError("Agent profile changed during credential rotation")
    _reject_profile_symlinks(path)
    return _write_profile_path(path, payload, preserve_credentials=False)


def stage_profile_rotation(
    name: str, payload: dict[str, Any], *, expected_api_key: str
) -> tuple[dict[str, Any], bool]:
    pending_path = pending_rotation_path(name)
    existing = read_profile(name)
    _reject_profile_symlinks(pending_path)
    if pending_path.exists():
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        if not isinstance(pending, dict):
            raise ValueError("pending Agent credential rotation must contain an object")
        staged_profile = pending.get("profile")
        if not isinstance(staged_profile, dict):
            raise ValueError("pending Agent credential rotation is invalid")
        current_key = existing.get("api_key")
        if current_key not in {
            pending.get("expected_api_key"),
            staged_profile.get("api_key"),
        }:
            raise ValueError("pending Agent credential rotation does not match the profile")
        return staged_profile, False
    if existing.get("api_key") != expected_api_key:
        raise ValueError("Agent profile changed during credential rotation")
    _write_profile_path(
        pending_path,
        {"expected_api_key": expected_api_key, "profile": payload},
        preserve_credentials=False,
    )
    return payload, True


def finalize_profile_rotation(name: str) -> Path:
    pending_path = pending_rotation_path(name)
    _reject_profile_symlinks(pending_path)
    if not pending_path.is_file():
        raise ValueError("pending Agent credential rotation not found")
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    if not isinstance(pending, dict) or not isinstance(pending.get("profile"), dict):
        raise ValueError("pending Agent credential rotation is invalid")
    expected_api_key = str(pending.get("expected_api_key") or "")
    existing = read_profile(name)
    if existing.get("api_key") == pending["profile"].get("api_key"):
        path = profile_path(name)
    else:
        path = replace_profile_credentials(
            name,
            pending["profile"],
            expected_api_key=expected_api_key,
        )
    pending_path.unlink()
    dir_fd = os.open(pending_path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return path


def read_profile(name: str) -> dict[str, Any]:
    path = profile_path(name)
    _reject_profile_symlinks(path)
    if not path.is_file():
        raise ValueError(f"Agent profile not found: {name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Agent profile must contain an object")
    return payload


def new_keys() -> tuple[str, str]:
    return f"status_{secrets.token_urlsafe(32)}", f"agt_{secrets.token_urlsafe(32)}"
