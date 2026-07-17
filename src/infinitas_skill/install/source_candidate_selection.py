"""Candidate filtering and deterministic source preference rules."""

from __future__ import annotations

from typing import Any

JsonDict = dict[str, Any]


def candidate_sort_key(item: JsonDict) -> tuple[int, int, int, str, str]:
    stage_order = {"active": 0, "incubating": 1, "archived": 2}
    stage = item.get("stage")
    snapshot_created_at = item.get("snapshot_created_at")
    dir_name = item.get("dir_name")
    return (
        -int(item.get("registry_priority", 0)),
        0 if item.get("source_type") == "distribution-manifest" else 1,
        stage_order.get(stage, 9) if isinstance(stage, str) else 9,
        snapshot_created_at if isinstance(snapshot_created_at, str) else "",
        dir_name if isinstance(dir_name, str) else "",
    )


def archived_snapshot_sort_key(item: JsonDict) -> tuple[int, int, int, str]:
    raw_ts = item.get("snapshot_created_at")
    ts = raw_ts if isinstance(raw_ts, str) else ""
    ts_num = int(ts.translate(str.maketrans("", "", "T-Z:"))) if ts else 0
    raw_dir_name = item.get("dir_name")
    return (
        -int(item.get("registry_priority", 0)),
        0 if item.get("source_type") == "distribution-manifest" else 1,
        -ts_num,
        raw_dir_name if isinstance(raw_dir_name, str) else "",
    )


def matching_candidates(
    loaded_candidates: list[JsonDict],
    *,
    requested_name: str,
    requested_publisher: str | None,
    requested_identity: str,
    allow_incubating: bool,
) -> list[JsonDict]:
    candidates = (
        [item for item in loaded_candidates if item.get("qualified_name") == requested_identity]
        if requested_publisher
        else [item for item in loaded_candidates if item.get("name") == requested_name]
    )
    return (
        candidates
        if allow_incubating
        else [item for item in candidates if item.get("stage") != "incubating"]
    )


def select_candidate(
    candidates: list[JsonDict],
    *,
    requested_name: str,
    requested_identity: str,
    requested_publisher: str | None,
    version: str | None,
) -> tuple[JsonDict | None, str | None]:
    if not version:
        active = [item for item in candidates if item.get("stage") == "active"]
        active.sort(key=candidate_sort_key)
        return (active[0], "active-default") if active else (None, None)

    exact = [item for item in candidates if item.get("version") == version]
    snapshot_refs = [f"{requested_name}@{version}"]
    if requested_publisher:
        snapshot_refs.insert(0, f"{requested_identity}@{version}")
    snapshots = [
        item
        for item in exact
        if item.get("stage") == "archived" and item.get("snapshot_of") in snapshot_refs
    ]
    if snapshots:
        snapshots.sort(key=archived_snapshot_sort_key)
        return snapshots[0], "archived-exact-snapshot"
    if exact:
        exact.sort(key=candidate_sort_key)
        return exact[0], "exact-version"
    return None, None
