"""Install manifest helpers for package-native install validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.skills.schema_version import (
    SUPPORTED_SCHEMA_VERSION,
    validate_schema_version,
)

MANIFEST_FILENAME = ".infinitas-skill-install-manifest.json"


class InstallManifestError(Exception):
    pass


def manifest_path_for(path_or_dir: str | Path) -> Path:
    path = Path(path_or_dir)
    if path.name == MANIFEST_FILENAME:
        return path.resolve()
    return (path / MANIFEST_FILENAME).resolve()


def default_install_manifest(repo: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "repo": repo,
        "updated_at": None,
        "skills": {},
        "history": {},
    }


def _normalize_install_entry(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InstallManifestError("install manifest entries must be objects")
    if value.get("identity_mode") == "legacy":
        raise InstallManifestError("legacy install manifest identity is not supported")
    if value.get("publisher") == "_legacy" or any(
        isinstance(item, str) and "/_legacy/" in item for item in value.values()
    ):
        raise InstallManifestError("legacy distribution paths are not supported")
    normalized = dict(value)
    last_checked_at = value.get("last_checked_at")
    normalized["last_checked_at"] = (
        last_checked_at if isinstance(last_checked_at, str) and last_checked_at else None
    )
    return normalized


def normalize_install_manifest(payload: object, *, repo: str | None = None) -> dict[str, Any]:
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise InstallManifestError("install manifest must be a JSON object")
    _schema_version, errors = validate_schema_version(payload)
    if errors:
        raise InstallManifestError("; ".join(errors))
    normalized = dict(payload)
    normalized["schema_version"] = SUPPORTED_SCHEMA_VERSION
    if normalized.get("repo") is None:
        normalized["repo"] = repo
    normalized.setdefault("updated_at", None)

    skills = normalized.get("skills")
    if skills is None:
        normalized["skills"] = {}
    elif not isinstance(skills, dict):
        raise InstallManifestError("install manifest skills must be an object")
    else:
        normalized["skills"] = {
            key: _normalize_install_entry(value) for key, value in skills.items()
        }

    history = normalized.get("history")
    if history is None:
        normalized["history"] = {}
    elif not isinstance(history, dict):
        raise InstallManifestError("install manifest history must be an object")
    else:
        normalized["history"] = {
            key: [_normalize_install_entry(item) for item in value]
            if isinstance(value, list)
            else value
            for key, value in history.items()
        }

    return normalized


def load_install_manifest(
    path_or_dir: str | Path,
    *,
    repo: str | None = None,
    allow_missing: bool = False,
) -> dict[str, Any]:
    manifest_path = manifest_path_for(path_or_dir)
    if not manifest_path.exists():
        if allow_missing:
            return default_install_manifest(repo=repo)
        raise InstallManifestError(f"missing manifest: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise InstallManifestError(f"invalid install manifest JSON: {exc}") from exc
    return normalize_install_manifest(payload, repo=repo)


def write_install_manifest(
    path_or_dir: str | Path, payload: object, *, repo: str | None = None
) -> Path:
    manifest_path = manifest_path_for(path_or_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_install_manifest(payload, repo=repo)
    manifest_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path
