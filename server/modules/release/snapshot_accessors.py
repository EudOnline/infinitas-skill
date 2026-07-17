"""Snapshot accessor helpers for the release materializer.

Pure accessor functions that extract fields from the release snapshot
composite object.  Zero side effects.
"""

from __future__ import annotations

from typing import Any

from server.modules.release.service import ReleaseSnapshot


def snapshot_content_id(snapshot: ReleaseSnapshot) -> int:
    return int(snapshot.skill_version.content_id)


def snapshot_metadata(snapshot: ReleaseSnapshot) -> dict[str, Any]:
    value = snapshot.manifest.get("metadata") if isinstance(snapshot.manifest, dict) else None
    if isinstance(value, dict):
        return value
    return {}


def snapshot_source_ref(snapshot: ReleaseSnapshot) -> str:
    value = snapshot.manifest.get("content_id") if isinstance(snapshot.manifest, dict) else None
    return f"content:{value}" if value else f"content-row:{snapshot_content_id(snapshot)}"
