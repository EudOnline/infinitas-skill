"""Snapshot accessor helpers for the release materializer.

Pure accessor functions that extract fields from the release snapshot
composite object.  Zero side effects.
"""

from __future__ import annotations

from typing import Any

from server.modules.release.service import ReleaseSnapshot


def snapshot_content_mode(snapshot: ReleaseSnapshot) -> str:
    value = snapshot.manifest.get("content_mode") if isinstance(snapshot.manifest, dict) else None
    if value:
        return str(value)
    return "external_ref"


def snapshot_content_ref(snapshot: ReleaseSnapshot) -> str:
    value = snapshot.manifest.get("content_ref") if isinstance(snapshot.manifest, dict) else None
    if value:
        return str(value)
    return ""


def snapshot_content_artifact_id(snapshot: ReleaseSnapshot) -> int | None:
    value = (
        snapshot.manifest.get("content_artifact_id")
        if isinstance(snapshot.manifest, dict)
        else None
    )
    if value is not None:
        return int(value)
    return None


def snapshot_metadata(snapshot: ReleaseSnapshot) -> dict[str, Any]:
    value = snapshot.manifest.get("metadata") if isinstance(snapshot.manifest, dict) else None
    if isinstance(value, dict):
        return value
    return {}


def snapshot_source_ref(snapshot: ReleaseSnapshot) -> str:
    content_ref = snapshot_content_ref(snapshot)
    if content_ref:
        return content_ref
    artifact_id = snapshot_content_artifact_id(snapshot)
    if artifact_id is not None:
        return f"artifact:{artifact_id}"
    return ""
