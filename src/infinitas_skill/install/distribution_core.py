"""Pure distribution parsing, hashing, and bundle-inspection primitives."""

from __future__ import annotations

import hashlib
import json
import platform
import tarfile
from pathlib import Path
from typing import Any


class DistributionError(Exception):
    """Raised when a distribution artifact violates its signed contract."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _gzip_mtime(path: str | Path) -> int:
    header = Path(path).read_bytes()[:8]
    if len(header) < 8 or header[:2] != b"\x1f\x8b":
        raise DistributionError(f"invalid gzip header: {path}")
    return int.from_bytes(header[4:8], "little")


def inspect_distribution_bundle(
    bundle_path: str | Path, *, expected_root: str | None = None
) -> dict[str, Any]:
    bundle = Path(bundle_path).resolve()
    file_manifest: list[dict[str, Any]] = []
    tar_mtimes: set[int | float] = set()
    tar_uids: set[int] = set()
    tar_gids: set[int] = set()
    tar_unames: set[str] = set()
    tar_gnames: set[str] = set()

    with tarfile.open(bundle, mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            member_path = Path(member.name)
            if expected_root:
                if not member_path.parts or member_path.parts[0] != expected_root:
                    raise DistributionError(
                        f"bundle member {member.name!r} is outside expected root {expected_root!r}"
                    )
                rel_path = str(Path(*member_path.parts[1:]))
            else:
                rel_path = member.name
            if not rel_path:
                raise DistributionError(
                    f"bundle member {member.name!r} resolved to an empty relative path"
                )
            handle = archive.extractfile(member)
            if handle is None:
                raise DistributionError(f"could not read bundle member: {member.name}")
            data = handle.read()
            file_manifest.append(
                {
                    "path": rel_path,
                    "sha256": _sha256_bytes(data),
                    "size": member.size,
                    "mode": f"{member.mode & 0o777:04o}",
                }
            )
            tar_mtimes.add(member.mtime)
            tar_uids.add(member.uid)
            tar_gids.add(member.gid)
            tar_unames.add(member.uname or "")
            tar_gnames.add(member.gname or "")

    file_manifest.sort(key=lambda item: str(item["path"]))
    return {
        "file_manifest": file_manifest,
        "build": {
            "archive_format": "tar.gz",
            "gzip_mtime": _gzip_mtime(bundle),
            "tar_mtime": min(tar_mtimes) if tar_mtimes else 0,
            "tar_uid": min(tar_uids) if tar_uids else 0,
            "tar_gid": min(tar_gids) if tar_gids else 0,
            "tar_uname": next(iter(tar_unames)) if len(tar_unames) == 1 else None,
            "tar_gname": next(iter(tar_gnames)) if len(tar_gnames) == 1 else None,
            "builder": {
                "python": platform.python_version(),
                "implementation": platform.python_implementation(),
            },
        },
    }


def normalize_file_manifest(entries: object) -> list[dict[str, Any]] | None:
    if not isinstance(entries, list):
        return None
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None
        normalized.append(
            {
                "path": entry.get("path"),
                "sha256": entry.get("sha256"),
                "size": entry.get("size"),
                "mode": entry.get("mode"),
            }
        )
    normalized.sort(key=lambda item: str(item.get("path") or ""))
    return normalized


def normalize_build(build: object, *, include_builder: bool = True) -> dict[str, Any] | None:
    if not isinstance(build, dict):
        return None
    normalized = {
        "archive_format": build.get("archive_format"),
        "gzip_mtime": build.get("gzip_mtime"),
        "tar_mtime": build.get("tar_mtime"),
        "tar_uid": build.get("tar_uid"),
        "tar_gid": build.get("tar_gid"),
        "tar_uname": build.get("tar_uname"),
        "tar_gname": build.get("tar_gname"),
    }
    if include_builder:
        normalized["builder"] = build.get("builder")
    return normalized


def reproducibility_summary(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    summary: dict[str, Any] = {}
    file_manifest = payload.get("file_manifest")
    if isinstance(file_manifest, list):
        summary["file_manifest_count"] = len(file_manifest)
    build = payload.get("build")
    if isinstance(build, dict):
        summary["build"] = build
        summary["build_archive_format"] = build.get("archive_format")
    bundle = payload.get("bundle")
    if isinstance(bundle, dict):
        for source, target in (
            ("path", "bundle_path"),
            ("sha256", "bundle_sha256"),
            ("file_count", "bundle_file_count"),
        ):
            value = bundle.get(source)
            if isinstance(value, (str, int)) and value != "":
                summary[target] = value
    return summary


def installed_integrity_capability_summary(payload: object) -> dict[str, str]:
    if isinstance(payload, dict):
        file_manifest = payload.get("file_manifest")
        if isinstance(file_manifest, list) and file_manifest:
            return {"installed_integrity_capability": "supported"}
    return {
        "installed_integrity_capability": "unknown",
        "installed_integrity_reason": "missing-signed-file-manifest",
    }


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DistributionError(f"expected JSON object: {path}")
    return payload


def relative_from_root(root: str | Path, path: str | Path) -> str:
    resolved_root = Path(root).resolve()
    resolved_path = Path(path).resolve()
    return (
        str(resolved_path.relative_to(resolved_root))
        if resolved_path.is_relative_to(resolved_root)
        else str(resolved_path)
    )


def resolve_manifest_ref(
    manifest_path: str | Path, reference: str | Path, root: str | Path | None = None
) -> Path:
    ref_path = Path(reference)
    if ref_path.is_absolute():
        return ref_path.resolve()
    if root is not None:
        root_candidate = (Path(root).resolve() / ref_path).resolve()
        if root_candidate.exists():
            return root_candidate
    return (Path(manifest_path).resolve().parent / ref_path).resolve()
