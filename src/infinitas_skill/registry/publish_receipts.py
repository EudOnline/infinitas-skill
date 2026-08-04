"""Durable receipt storage for resumable hosted publication."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from infinitas_skill.registry.publish_types import HostedPublishError

_RECEIPT_FIELDS = {
    "schema_version",
    "source_path",
    "base_url",
    "qualified_name",
    "version",
    "bundle_sha256",
    "state",
    "skill_id",
    "content_id",
    "version_id",
    "release_id",
    "exposure_id",
}


def receipt_path(
    source_dir: str | Path,
    *,
    base_url: str,
    slug: str,
    version: str,
    explicit_path: str | Path | None,
) -> Path:
    if explicit_path is not None:
        return Path(explicit_path).expanduser().resolve()
    state_root = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
    ).expanduser()
    identity = f"{Path(source_dir).expanduser().resolve()}\0{base_url.rstrip('/')}\0{version}"
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:12]
    safe_version = re.sub(r"[^A-Za-z0-9._-]", "_", version)
    return state_root / "infinitas" / "publish" / f"{slug}-{safe_version}-{suffix}.json"


def _load_receipt(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedPublishError(f"could not read publish receipt {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise HostedPublishError(f"publish receipt {path} is invalid")
    return {key: payload[key] for key in _RECEIPT_FIELDS if key in payload}


def save_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    filtered = {key: receipt[key] for key in _RECEIPT_FIELDS if key in receipt}
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(filtered, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(0o600)
        os.replace(temp_path, path)
        path.chmod(0o600)
    finally:
        temp_path.unlink(missing_ok=True)


def update_receipt(path: Path, receipt: dict[str, Any], **changes: Any) -> None:
    receipt.update(changes)
    save_receipt(path, receipt)


def prepare_receipt(
    path: Path,
    *,
    source_dir: str | Path,
    base_url: str,
    qualified_name: str,
    version: str,
    bundle_sha256: str,
    require_existing: bool,
) -> dict[str, Any]:
    expected = {
        "schema_version": 1,
        "source_path": str(Path(source_dir).expanduser().resolve()),
        "base_url": base_url.rstrip("/"),
        "qualified_name": qualified_name,
        "version": version,
        "bundle_sha256": bundle_sha256,
    }
    if not path.exists():
        if require_existing:
            raise HostedPublishError(f"publish receipt does not exist: {path}")
        return {**expected, "state": "prepared"}
    receipt = _load_receipt(path)
    mismatches = [key for key, value in expected.items() if receipt.get(key) != value]
    if mismatches:
        raise HostedPublishError(
            "publish receipt does not match the current source: " + ", ".join(mismatches)
        )
    return receipt
