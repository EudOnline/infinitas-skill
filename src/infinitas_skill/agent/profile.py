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


def verifier(raw: str) -> str:
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fingerprint(api_verifier: str) -> str:
    return hashlib.sha256(
        f"infinitas-agent-fingerprint-v1\0{api_verifier}".encode("utf-8")
    ).hexdigest()[:16]


def write_profile(name: str, payload: dict[str, Any]) -> Path:
    path = profile_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
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


def read_profile(name: str) -> dict[str, Any]:
    path = profile_path(name)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Agent profile not found: {name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Agent profile must contain an object")
    return payload


def new_keys() -> tuple[str, str]:
    return f"status_{secrets.token_urlsafe(32)}", f"agt_{secrets.token_urlsafe(32)}"
