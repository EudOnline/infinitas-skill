"""Attestation and provenance state helpers for release readiness checks."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from infinitas_skill.legacy import ROOT, ensure_legacy_scripts_on_path

ensure_legacy_scripts_on_path(ROOT)

skill_identity_lib = importlib.import_module("skill_identity_lib")
transparency_log_lib = importlib.import_module("transparency_log_lib")

normalize_skill_identity = skill_identity_lib.normalize_skill_identity

TransparencyLogError = transparency_log_lib.TransparencyLogError
summarize_transparency_log_state = transparency_log_lib.summarize_transparency_log_state


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _release_artifact_paths(root, meta):
    identity = normalize_skill_identity(meta)
    publisher = identity.get("publisher") or "_legacy"
    name = meta.get("name")
    version = meta.get("version")
    root_path = Path(root)
    return {
        "provenance": root_path / "catalog" / "provenance" / f"{name}-{version}.json",
        "manifest": (
            root_path / "catalog" / "distributions" / publisher / name / version / "manifest.json"
        ),
    }


def _normalize_file_manifest(entries):
    if not isinstance(entries, list):
        return None
    normalized = []
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
    normalized.sort(key=lambda item: item.get("path") or "")
    return normalized


def _normalize_build(build):
    if not isinstance(build, dict):
        return None
    return {
        "archive_format": build.get("archive_format"),
        "gzip_mtime": build.get("gzip_mtime"),
        "tar_mtime": build.get("tar_mtime"),
        "tar_uid": build.get("tar_uid"),
        "tar_gid": build.get("tar_gid"),
        "tar_uname": build.get("tar_uname"),
        "tar_gname": build.get("tar_gname"),
        "builder": build.get("builder"),
    }


def collect_reproducibility_state(root, meta):
    paths = _release_artifact_paths(root, meta)
    root_path = Path(root)
    summary = {
        "available": False,
        "consistent": True,
        "issues": [],
        "provenance_path": str(paths["provenance"].relative_to(root_path))
        if paths["provenance"].exists()
        else None,
        "manifest_path": (
            str(paths["manifest"].relative_to(root_path)) if paths["manifest"].exists() else None
        ),
        "bundle_path": None,
        "bundle_file_count": None,
        "file_manifest_count": 0,
        "archive_format": None,
    }

    provenance_distribution = None
    if paths["provenance"].exists():
        provenance_payload = load_json(paths["provenance"])
        provenance_distribution = provenance_payload.get("distribution") or {}
        bundle = provenance_distribution.get("bundle") or {}
        if isinstance(bundle, dict):
            summary["bundle_path"] = bundle.get("path")
            summary["bundle_file_count"] = bundle.get("file_count")
        file_manifest = provenance_distribution.get("file_manifest")
        if isinstance(file_manifest, list):
            summary["file_manifest_count"] = len(file_manifest)
            summary["available"] = True
        build = provenance_distribution.get("build")
        if isinstance(build, dict):
            summary["archive_format"] = build.get("archive_format")
            summary["available"] = True

    manifest_payload = None
    if paths["manifest"].exists():
        manifest_payload = load_json(paths["manifest"])
        if summary["bundle_path"] is None:
            summary["bundle_path"] = (manifest_payload.get("bundle") or {}).get("path")
        if summary["bundle_file_count"] is None:
            summary["bundle_file_count"] = (manifest_payload.get("bundle") or {}).get("file_count")
        file_manifest = manifest_payload.get("file_manifest")
        if not summary["available"] and isinstance(file_manifest, list):
            summary["file_manifest_count"] = len(file_manifest)
            summary["available"] = True
        build = manifest_payload.get("build")
        if summary["archive_format"] is None and isinstance(build, dict):
            summary["archive_format"] = build.get("archive_format")
            summary["available"] = True

    if provenance_distribution is not None and manifest_payload is not None:
        normalized_signed_file_manifest = _normalize_file_manifest(
            provenance_distribution.get("file_manifest")
        )
        normalized_manifest_file_manifest = _normalize_file_manifest(
            manifest_payload.get("file_manifest")
        )
        if (
            normalized_signed_file_manifest is not None
            or normalized_manifest_file_manifest is not None
        ):
            if normalized_signed_file_manifest != normalized_manifest_file_manifest:
                summary["issues"].append(
                    "distribution file manifest does not match signed attestation"
                )

        normalized_signed_build = _normalize_build(provenance_distribution.get("build"))
        normalized_manifest_build = _normalize_build(manifest_payload.get("build"))
        if normalized_signed_build is not None or normalized_manifest_build is not None:
            if normalized_signed_build != normalized_manifest_build:
                summary["issues"].append(
                    "distribution build metadata does not match signed attestation"
                )

    summary["consistent"] = not summary["issues"]
    return summary


def collect_transparency_log_state(root, meta):
    provenance_path = _release_artifact_paths(root, meta)["provenance"]
    if not provenance_path.exists():
        return None
    payload = load_json(provenance_path)
    try:
        summary = summarize_transparency_log_state(provenance_path, payload=payload, root=root)
    except TransparencyLogError as exc:
        return {
            "mode": (
                ((payload.get("transparency_log") or {}).get("mode"))
                if isinstance(payload.get("transparency_log"), dict)
                else "unknown"
            ),
            "required": bool(
                ((payload.get("transparency_log") or {}).get("required"))
                if isinstance(payload.get("transparency_log"), dict)
                else False
            ),
            "entry_path": (
                ((payload.get("transparency_log") or {}).get("entry_path"))
                if isinstance(payload.get("transparency_log"), dict)
                else None
            ),
            "published": False,
            "verified": False,
            "entry_id": None,
            "log_index": None,
            "integrated_time": None,
            "log_endpoint": None,
            "error": str(exc),
        }
    return summary


__all__ = [
    "TransparencyLogError",
    "collect_reproducibility_state",
    "collect_transparency_log_state",
]
