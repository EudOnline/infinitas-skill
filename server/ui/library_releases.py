from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from server.models import Release
from server.modules.access.authn import AccessContext
from server.modules.release import service as release_service
from server.ui.formatting import humanize_identifier, humanize_timestamp, load_json_object
from server.ui.library_access import (
    credential_is_active,
    credential_is_share_secret,
    grant_is_active,
)
from server.ui.library_objects import object_payload, visibility_payload
from server.ui.library_scope import LibraryScope, iso_stamp, load_library_scope
from server.ui.navigation import _build_exposure_policy, _derive_exposure_action_state


def release_platform_compatibility(release: Release) -> dict[str, Any]:
    return load_json_object(release.platform_compatibility_json)


def build_release_artifact_rows(
    db: Session,
    *,
    release: Release,
) -> list[dict[str, Any]]:
    return [
        {
            "id": artifact.id,
            "kind": humanize_identifier(artifact.kind),
            "sha256": artifact.sha256 or "-",
            "size_bytes": str(artifact.size_bytes) if artifact.size_bytes is not None else "-",
            "storage_uri": artifact.storage_uri or "-",
        }
        for artifact in release_service.get_current_artifacts_for_release(db, release)
    ]


def build_release_visibility_rows(
    scope: LibraryScope,
    *,
    release: Release,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for exposure in scope.exposures_by_release_id.get(release.id, []):
        review_case = (scope.review_cases_by_exposure_id.get(exposure.id) or [None])[0]
        review_case_state = str(getattr(review_case, "state", None) or "none")
        share_count = 0
        token_count = 0
        for grant in scope.grants_by_exposure_id.get(exposure.id, []):
            if grant.grant_type == "link":
                if grant_is_active(grant, load_json_object(grant.constraints_json)):
                    share_count += 1
                continue
            for credential in scope.credentials_by_grant_id.get(grant.id, []):
                if credential_is_share_secret(credential):
                    continue
                if credential_is_active(credential, grant):
                    token_count += 1
        rows.append(
            {
                "id": exposure.id,
                "visibility": exposure.audience_type,
                "listing_mode": exposure.listing_mode,
                "listing_mode_raw": exposure.listing_mode,
                "install_mode": exposure.install_mode,
                "install_mode_raw": exposure.install_mode,
                "state": exposure.state,
                "state_raw": exposure.state,
                "share_count": share_count,
                "token_count": token_count,
                "review_case_state_raw": review_case_state,
                **_derive_exposure_action_state(
                    exposure=exposure,
                    review_case_state=review_case_state,
                ),
            }
        )
    return rows


def release_distribution_summary(
    scope: LibraryScope,
    *,
    release: Release,
    artifact_rows: list[dict[str, Any]],
    visibility_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    share_count = sum(int(item["share_count"]) for item in visibility_rows)
    token_count = sum(int(item["token_count"]) for item in visibility_rows)
    platform_compatibility = release_platform_compatibility(release)
    canonical_runtime = platform_compatibility.get("canonical_runtime") or {}
    blocking_platforms = platform_compatibility.get("blocking_platforms") or []
    grant_access_ready = any(
        exposure.audience_type == "grant"
        and exposure.state == "active"
        and exposure.install_mode == "enabled"
        for exposure in scope.exposures_by_release_id.get(release.id, [])
    )
    return {
        "artifacts_count": len(artifact_rows),
        "visibility_count": len(visibility_rows),
        "share_count": share_count,
        "token_count": token_count,
        "install_target": platform_compatibility.get("canonical_runtime_platform"),
        "install_readiness": canonical_runtime.get("freshness_state"),
        "blocking_count": len(blocking_platforms),
        "blocking_platforms": blocking_platforms,
        "grant_access_ready": grant_access_ready,
    }


def list_library_releases_from_scope(
    scope: LibraryScope,
    *,
    skill_id: int,
) -> list[dict[str, Any]]:
    versions = {
        version.id: version
        for version in scope.versions_by_skill_id.get(skill_id, [])
    }
    rows: list[dict[str, Any]] = []
    for release in scope.releases_by_skill_id.get(skill_id, []):
        exposure = next(iter(scope.exposures_by_release_id.get(release.id, [])), None)
        version = versions.get(release.skill_version_id)
        rows.append(
            {
                "release_id": release.id,
                "version": version.version if version is not None else None,
                "state": release.state,
                "created_at": humanize_timestamp(iso_stamp(release.created_at)),
                "ready_at": humanize_timestamp(iso_stamp(release.ready_at)),
                "visibility": visibility_payload(exposure),
            }
        )
    return rows


def list_library_releases(
    db: Session,
    *,
    actor: AccessContext,
    object_id: int,
) -> list[dict[str, Any]] | None:
    scope = load_library_scope(db, actor=actor)
    if not any(item.id == object_id for item in scope.skills):
        return None
    return list_library_releases_from_scope(scope, skill_id=object_id)


def get_library_release_detail(
    db: Session,
    *,
    actor: AccessContext,
    object_id: int,
    release_id: int,
) -> dict[str, Any] | None:
    scope = load_library_scope(db, actor=actor)
    skill = next((item for item in scope.skills if item.id == object_id), None)
    if skill is None:
        return None
    version_map = {
        version.id: version
        for version in scope.versions_by_skill_id.get(skill.id, [])
    }
    release = next(
        (item for item in scope.releases_by_skill_id.get(object_id, []) if item.id == release_id),
        None,
    )
    if release is None:
        return None
    version = version_map.get(release.skill_version_id)
    exposure = next(iter(scope.exposures_by_release_id.get(release.id, [])), None)
    artifact_rows = build_release_artifact_rows(db, release=release)
    visibility_rows = build_release_visibility_rows(scope, release=release)
    distribution_summary = release_distribution_summary(
        scope,
        release=release,
        artifact_rows=artifact_rows,
        visibility_rows=visibility_rows,
    )
    return {
        "object": object_payload(scope, skill),
        "release": {
            "id": release.id,
            "version": version.version if version is not None else f"release-{release.id}",
            "visibility": (
                exposure.audience_type
                if exposure is not None and exposure.audience_type
                else "private"
            ),
            "created_at": humanize_timestamp(iso_stamp(release.created_at)),
            "ready_at": humanize_timestamp(iso_stamp(release.ready_at)),
            "readiness_state": release.state or "unknown",
            "exposure_policy": _build_exposure_policy(),
            **distribution_summary,
        },
        "artifact_rows": artifact_rows,
        "visibility_rows": visibility_rows,
    }
