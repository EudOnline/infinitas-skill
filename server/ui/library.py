from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import (
    AccessGrant,
    AgentCodeSpec,
    AgentPresetSpec,
    Credential,
    Exposure,
    Principal,
    RegistryObject,
    Release,
    ReviewCase,
    Skill,
    SkillVersion,
)
from server.modules.access.authn import AccessContext
from server.modules.release import service as release_service
from server.ui.formatting import (
    humanize_identifier,
    humanize_timestamp,
    load_json_list,
    load_json_object,
)
from server.ui.i18n import pick_lang, with_lang
from server.ui.navigation import _build_exposure_policy, _derive_exposure_action_state


@dataclass(frozen=True)
class LibraryScope:
    objects: list[RegistryObject]
    principals_by_id: dict[int, Principal]
    skills_by_object_id: dict[int, Skill]
    versions_by_skill_id: dict[int, list[SkillVersion]]
    releases_by_object_id: dict[int, list[Release]]
    exposures_by_release_id: dict[int, list[Exposure]]
    review_cases_by_exposure_id: dict[int, list[ReviewCase]]
    grants_by_exposure_id: dict[int, list[AccessGrant]]
    credentials_by_grant_id: dict[int, list[Credential]]
    preset_specs_by_object_id: dict[int, AgentPresetSpec]
    code_specs_by_object_id: dict[int, AgentCodeSpec]


def _group_by(items: list[object], key_name: str) -> dict[int, list[object]]:
    grouped: dict[int, list[object]] = {}
    for item in items:
        key = getattr(item, key_name, None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(item)
    return grouped


def _scope_filter_for_actor(query, *, actor: AccessContext):
    if actor.user is not None and actor.user.role == "maintainer":
        return query
    principal_id = actor.principal.id if actor.principal is not None else None
    if principal_id is None:
        return query.where(RegistryObject.id < 0)
    return query.where(RegistryObject.namespace_id == principal_id)


def load_library_scope(db: Session, *, actor: AccessContext) -> LibraryScope:
    object_query = select(RegistryObject).order_by(
        RegistryObject.updated_at.desc(),
        RegistryObject.id.desc(),
    )
    objects = db.scalars(_scope_filter_for_actor(object_query, actor=actor)).all()
    object_ids = [item.id for item in objects]
    principal_ids = sorted({item.namespace_id for item in objects})

    principals = []
    if principal_ids:
        principals = db.scalars(
            select(Principal)
            .where(Principal.id.in_(principal_ids))
            .order_by(Principal.id.asc())
        ).all()

    skills = []
    if object_ids:
        skills = db.scalars(
            select(Skill)
            .where(Skill.registry_object_id.in_(object_ids))
            .order_by(Skill.id.desc())
        ).all()
    skills_by_object_id = {
        int(skill.registry_object_id): skill
        for skill in skills
        if skill.registry_object_id
    }
    skill_ids = [skill.id for skill in skills]

    versions = []
    if skill_ids:
        versions = db.scalars(
            select(SkillVersion)
            .where(SkillVersion.skill_id.in_(skill_ids))
            .order_by(SkillVersion.created_at.desc(), SkillVersion.id.desc())
        ).all()
    versions_by_skill_id = _group_by(versions, "skill_id")

    version_ids = [version.id for version in versions]
    releases = []
    if object_ids or version_ids:
        release_query = select(Release).order_by(Release.created_at.desc(), Release.id.desc())
        if object_ids and version_ids:
            release_query = release_query.where(
                (Release.registry_object_id.in_(object_ids))
                | (Release.skill_version_id.in_(version_ids))
            )
        elif object_ids:
            release_query = release_query.where(Release.registry_object_id.in_(object_ids))
        else:
            release_query = release_query.where(Release.skill_version_id.in_(version_ids))
        releases = db.scalars(release_query).all()

    inferred_object_ids_by_version: dict[int, int] = {}
    for version in versions:
        skill = next((item for item in skills if item.id == version.skill_id), None)
        if skill is not None and skill.registry_object_id is not None:
            inferred_object_ids_by_version[version.id] = int(skill.registry_object_id)

    releases_by_object_id: dict[int, list[Release]] = {}
    for release in releases:
        object_id = release.registry_object_id or inferred_object_ids_by_version.get(
            release.skill_version_id
        )
        if object_id is None:
            continue
        releases_by_object_id.setdefault(int(object_id), []).append(release)

    release_ids = [release.id for release in releases]
    exposures = []
    if release_ids:
        exposures = db.scalars(
            select(Exposure)
            .where(Exposure.release_id.in_(release_ids))
            .order_by(Exposure.id.desc())
        ).all()
    exposures_by_release_id = _group_by(exposures, "release_id")

    exposure_ids = [exposure.id for exposure in exposures]
    review_cases = []
    if exposure_ids:
        review_cases = db.scalars(
            select(ReviewCase)
            .where(ReviewCase.exposure_id.in_(exposure_ids))
            .order_by(ReviewCase.id.desc())
        ).all()
    review_cases_by_exposure_id = _group_by(review_cases, "exposure_id")

    grants = []
    if exposure_ids:
        grants = db.scalars(
            select(AccessGrant)
            .where(AccessGrant.exposure_id.in_(exposure_ids))
            .order_by(AccessGrant.id.desc())
        ).all()
    grants_by_exposure_id = _group_by(grants, "exposure_id")

    grant_ids = [grant.id for grant in grants]
    credentials = []
    if grant_ids:
        credentials = db.scalars(
            select(Credential)
            .where(Credential.grant_id.in_(grant_ids))
            .order_by(Credential.id.desc())
        ).all()
    credentials_by_grant_id = _group_by(credentials, "grant_id")

    preset_specs = []
    code_specs = []
    if object_ids:
        preset_specs = db.scalars(
            select(AgentPresetSpec).where(AgentPresetSpec.registry_object_id.in_(object_ids))
        ).all()
        code_specs = db.scalars(
            select(AgentCodeSpec).where(AgentCodeSpec.registry_object_id.in_(object_ids))
        ).all()

    return LibraryScope(
        objects=objects,
        principals_by_id={principal.id: principal for principal in principals},
        skills_by_object_id=skills_by_object_id,
        versions_by_skill_id=versions_by_skill_id,
        releases_by_object_id=releases_by_object_id,
        exposures_by_release_id=exposures_by_release_id,
        review_cases_by_exposure_id=review_cases_by_exposure_id,
        grants_by_exposure_id=grants_by_exposure_id,
        credentials_by_grant_id=credentials_by_grant_id,
        preset_specs_by_object_id={spec.registry_object_id: spec for spec in preset_specs},
        code_specs_by_object_id={spec.registry_object_id: spec for spec in code_specs},
    )


def _iso_stamp(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _credential_state(credential: Credential, grant: AccessGrant | None = None) -> str:
    now = datetime.now(timezone.utc)
    if credential.revoked_at is not None:
        return "revoked"
    expires_at = _parse_datetime(credential.expires_at)
    if expires_at is not None and expires_at <= now:
        return "expired"
    if grant is not None and grant.state and grant.state != "active":
        return grant.state
    return "active"


def _grant_state(grant: AccessGrant, constraints: dict[str, Any]) -> str:
    if grant.state and grant.state != "active":
        return grant.state
    expires_at = _parse_datetime(constraints.get("expires_at"))
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
        return "expired"
    return "active"


def _credential_is_active(credential: Credential, grant: AccessGrant | None = None) -> bool:
    return _credential_state(credential, grant) == "active"


def _grant_is_active(grant: AccessGrant, constraints: dict[str, Any]) -> bool:
    return _grant_state(grant, constraints) == "active"


def _credential_is_share_secret(credential: Credential) -> bool:
    return credential.type in {"share_password", "share_secret"}


def _scopes_for_credential(credential: Credential) -> set[str]:
    return {item.strip() for item in load_json_list(credential.scopes_json) if item.strip()}


def _token_type_for_credential(credential: Credential) -> str:
    scopes = _scopes_for_credential(credential)
    if any(
        scope.endswith(":write")
        or scope in {"authoring:write", "publish:write", "registry:publish"}
        for scope in scopes
    ):
        return "publisher"
    return "reader"


def _iter_object_release_rows(scope: LibraryScope):
    for registry_object in scope.objects:
        skill = scope.skills_by_object_id.get(registry_object.id)
        version_map = (
            {version.id: version for version in scope.versions_by_skill_id.get(skill.id, [])}
            if skill is not None
            else {}
        )
        for release in scope.releases_by_object_id.get(registry_object.id, []):
            yield registry_object, release, version_map.get(release.skill_version_id)


def _build_token_rows_from_scope(
    scope: LibraryScope,
    *,
    lang: str,
    object_id: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for registry_object, release, version in _iter_object_release_rows(scope):
        if object_id is not None and registry_object.id != object_id:
            continue
        for exposure in scope.exposures_by_release_id.get(release.id, []):
            for grant in scope.grants_by_exposure_id.get(exposure.id, []):
                if grant.grant_type == "link":
                    continue
                constraints = load_json_object(grant.constraints_json)
                for credential in scope.credentials_by_grant_id.get(grant.id, []):
                    if _credential_is_share_secret(credential):
                        continue
                    state = _credential_state(credential, grant)
                    revoked_at = _parse_datetime(credential.revoked_at)
                    sort_at = (
                        revoked_at
                        or _parse_datetime(credential.last_used_at)
                        or _parse_datetime(credential.created_at)
                    )
                    rows.append(
                        {
                            "id": credential.id,
                            "token_type": _token_type_for_credential(credential),
                            "object_id": registry_object.id,
                            "object_name": registry_object.display_name,
                            "object_href": with_lang(f"/library/{registry_object.id}", lang),
                            "release_id": release.id,
                            "release_version": version.version if version is not None else None,
                            "label": constraints.get("label") or "",
                            "grant_id": grant.id,
                            "state": state,
                            "can_revoke": state == "active",
                            "created_at": humanize_timestamp(_iso_stamp(credential.created_at)),
                            "last_used_at": humanize_timestamp(_iso_stamp(credential.last_used_at)),
                            "revoked_at": humanize_timestamp(_iso_stamp(credential.revoked_at)),
                            "_sort_at": sort_at or datetime.min.replace(tzinfo=timezone.utc),
                        }
                    )
    rows.sort(key=lambda item: item["_sort_at"], reverse=True)
    return rows


def _build_share_rows_from_scope(
    scope: LibraryScope,
    *,
    lang: str,
    object_id: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for registry_object, release, version in _iter_object_release_rows(scope):
        if object_id is not None and registry_object.id != object_id:
            continue
        for exposure in scope.exposures_by_release_id.get(release.id, []):
            for grant in scope.grants_by_exposure_id.get(exposure.id, []):
                if grant.grant_type != "link":
                    continue
                constraints = load_json_object(grant.constraints_json)
                credentials = scope.credentials_by_grant_id.get(grant.id, [])
                rows.append(
                    {
                        "id": grant.id,
                        "object_id": registry_object.id,
                        "object_name": registry_object.display_name,
                        "object_href": with_lang(f"/library/{registry_object.id}", lang),
                        "release_id": release.id,
                        "release_version": version.version if version is not None else None,
                        "label": constraints.get("label") or "",
                        "expiry": humanize_timestamp(constraints.get("expires_at")),
                        "has_password": bool(
                            constraints.get("temporary_password")
                            or constraints.get("password")
                            or any(_credential_is_share_secret(item) for item in credentials)
                        ),
                        "usage_count": int(constraints.get("usage_count") or 0),
                        "usage_limit": (
                            int(constraints["usage_limit"])
                            if constraints.get("usage_limit") is not None
                            else None
                        ),
                        "state": _grant_state(grant, constraints),
                        "can_revoke": _grant_is_active(grant, constraints),
                        "_sort_at": _parse_datetime(grant.created_at)
                        or datetime.min.replace(tzinfo=timezone.utc),
                    }
                )
    rows.sort(key=lambda item: item["_sort_at"], reverse=True)
    return rows


def _build_token_activity_rows_from_token_rows(
    token_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in token_rows:
        if row["state"] == "revoked":
            items.append(
                {
                    "event_type": "revoked",
                    "token_id": row["id"],
                    "title": f"{row['token_type']} token revoked",
                    "object_name": row["object_name"],
                    "timestamp": row["revoked_at"] or row["created_at"],
                    "detail": f"{row['token_type']} token revoked for {row['object_name']}",
                    "_sort_at": row["_sort_at"],
                }
            )
        if row.get("last_used_at") and row["last_used_at"] != "-":
            items.append(
                {
                    "event_type": "used",
                    "token_id": row["id"],
                    "title": f"{row['token_type']} token used",
                    "object_name": row["object_name"],
                    "timestamp": row["last_used_at"],
                    "detail": f"{row['token_type']} token accessed {row['object_name']}",
                    "_sort_at": row["_sort_at"],
                }
            )
        items.append(
            {
                "event_type": "issued",
                "token_id": row["id"],
                "title": f"{row['token_type']} token issued",
                "object_name": row["object_name"],
                "timestamp": row["created_at"],
                "detail": f"{row['token_type']} token issued for {row['object_name']}",
                "_sort_at": row["_sort_at"],
            }
        )
    items.sort(key=lambda item: item["_sort_at"], reverse=True)
    return items


def _build_activity_rows_from_scope(scope: LibraryScope) -> list[dict[str, Any]]:
    token_rows = _build_token_rows_from_scope(scope, lang="en")
    token_activity_rows = _build_token_activity_rows_from_token_rows(token_rows)
    share_rows = _build_share_rows_from_scope(scope, lang="en")
    principal_labels = {key: value.slug for key, value in scope.principals_by_id.items()}

    items: list[dict[str, Any]] = []
    for registry_object, release, version in _iter_object_release_rows(scope):
        version_label = version.version if version is not None else f"release-{release.id}"
        for exposure in scope.exposures_by_release_id.get(release.id, []):
            sort_at = (
                _parse_datetime(exposure.activated_at)
                or _parse_datetime(exposure.ended_at)
                or _parse_datetime(release.ready_at)
                or datetime.min.replace(tzinfo=timezone.utc)
            )
            items.append(
                {
                    "event_type": "visibility",
                    "title": f"Visibility set to {exposure.audience_type}",
                    "description": (
                        f"{registry_object.display_name} {version_label} is {exposure.state} "
                        f"for {exposure.audience_type} access."
                    ),
                    "object_name": registry_object.display_name,
                    "actor": principal_labels.get(exposure.requested_by_principal_id),
                    "timestamp": humanize_timestamp(_iso_stamp(sort_at)),
                    "_sort_at": sort_at,
                }
            )
    for row in token_activity_rows:
        items.append(
            {
                "event_type": "token",
                "title": row["title"],
                "description": row["detail"],
                "object_name": row.get("object_name"),
                "actor": None,
                "timestamp": row["timestamp"],
                "_sort_at": row["_sort_at"],
            }
        )
    for row in share_rows:
        items.append(
            {
                "event_type": "share",
                "title": "Share link issued",
                "description": (
                    f"{row['object_name']} {row['release_version'] or row['release_id']} "
                    f"share is {row['state']}."
                ),
                "object_name": row["object_name"],
                "actor": None,
                "timestamp": humanize_timestamp(
                    _iso_stamp(row["_sort_at"]) if isinstance(row["_sort_at"], datetime) else None
                ),
                "_sort_at": row["_sort_at"],
            }
        )
    items.sort(key=lambda item: item["_sort_at"], reverse=True)
    return items


def _release_platform_compatibility(release: Release) -> dict[str, Any]:
    return load_json_object(release.platform_compatibility_json)


def _build_release_artifact_rows(
    db: Session,
    *,
    release: Release,
) -> list[dict[str, Any]]:
    return [
        {
            "id": artifact.id,
            "kind": humanize_identifier(artifact.kind),
            "sha256": artifact.sha256 or "-",
            "size_bytes": str(artifact.size_bytes),
            "storage_uri": artifact.storage_uri or "-",
        }
        for artifact in release_service.get_current_artifacts_for_release(db, release)
    ]


def _build_release_visibility_rows(
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
                if _grant_is_active(grant, load_json_object(grant.constraints_json)):
                    share_count += 1
                continue
            for credential in scope.credentials_by_grant_id.get(grant.id, []):
                if _credential_is_share_secret(credential):
                    continue
                if _credential_is_active(credential, grant):
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


def _release_distribution_summary(
    scope: LibraryScope,
    *,
    release: Release,
    artifact_rows: list[dict[str, Any]],
    visibility_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    share_count = sum(int(item["share_count"]) for item in visibility_rows)
    token_count = sum(int(item["token_count"]) for item in visibility_rows)
    platform_compatibility = _release_platform_compatibility(release)
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


def _visibility_payload(exposure: Exposure | None) -> dict[str, Any]:
    if exposure is None:
        return {
            "audience_type": None,
            "listing_mode": None,
            "install_mode": None,
            "state": None,
        }
    return {
        "audience_type": exposure.audience_type,
        "listing_mode": exposure.listing_mode,
        "install_mode": exposure.install_mode,
        "state": exposure.state,
    }


def _current_release_payload(
    scope: LibraryScope,
    *,
    object_id: int,
    skill_id: int | None,
) -> dict[str, Any] | None:
    releases = scope.releases_by_object_id.get(object_id, [])
    if not releases:
        return None
    release = releases[0]
    version_label = None
    if skill_id is not None:
        versions = scope.versions_by_skill_id.get(skill_id, [])
        version_map = {version.id: version for version in versions}
        version = version_map.get(release.skill_version_id)
        if version is not None:
            version_label = version.version
    return {
        "release_id": release.id,
        "version": version_label,
        "state": release.state,
        "ready_at": _iso_stamp(release.ready_at),
    }


def _type_details(scope: LibraryScope, registry_object: RegistryObject) -> dict[str, Any]:
    if registry_object.kind == "agent_preset":
        spec = scope.preset_specs_by_object_id.get(registry_object.id)
        if spec is None:
            return {"kind": "agent_preset"}
        return {
            "kind": "agent_preset",
            "runtime_family": spec.runtime_family,
            "supported_memory_modes": load_json_list(spec.supported_memory_modes_json),
            "default_memory_mode": spec.default_memory_mode,
            "pinned_skill_dependencies": load_json_list(spec.pinned_skill_dependencies_json),
        }
    if registry_object.kind == "agent_code":
        spec = scope.code_specs_by_object_id.get(registry_object.id)
        if spec is None:
            return {"kind": "agent_code"}
        return {
            "kind": "agent_code",
            "runtime_family": spec.runtime_family,
            "language": spec.language,
            "entrypoint": spec.entrypoint,
            "external_source": load_json_object(spec.external_source_json),
        }
    skill = scope.skills_by_object_id.get(registry_object.id)
    return {
        "kind": "skill",
        "default_visibility_profile": (
            skill.default_visibility_profile if skill is not None else None
        ),
    }


def _object_payload(scope: LibraryScope, registry_object: RegistryObject) -> dict[str, Any]:
    skill = scope.skills_by_object_id.get(registry_object.id)
    current_release = _current_release_payload(
        scope,
        object_id=registry_object.id,
        skill_id=skill.id if skill is not None else None,
    )
    release_id = current_release["release_id"] if current_release is not None else None
    current_exposure = None
    if release_id is not None:
        exposures = scope.exposures_by_release_id.get(int(release_id), [])
        current_exposure = exposures[0] if exposures else None

    share_link_count = 0
    token_count = 0
    for release in scope.releases_by_object_id.get(registry_object.id, []):
        for exposure in scope.exposures_by_release_id.get(release.id, []):
            grants = scope.grants_by_exposure_id.get(exposure.id, [])
            for grant in grants:
                if grant.grant_type == "link":
                    if _grant_is_active(grant, load_json_object(grant.constraints_json)):
                        share_link_count += 1
                    continue
                for credential in scope.credentials_by_grant_id.get(grant.id, []):
                    if _credential_is_share_secret(credential):
                        continue
                    if _credential_is_active(credential, grant):
                        token_count += 1

    owner = scope.principals_by_id.get(registry_object.namespace_id)
    return {
        "id": registry_object.id,
        "kind": registry_object.kind,
        "kind_label": humanize_identifier(registry_object.kind),
        "slug": registry_object.slug,
        "display_name": registry_object.display_name,
        "summary": registry_object.summary or "",
        "owner": owner.slug if owner is not None else None,
        "updated_at": _iso_stamp(registry_object.updated_at),
        "current_release": current_release,
        "current_visibility": _visibility_payload(current_exposure),
        "token_count": token_count,
        "share_link_count": share_link_count,
    }


def list_library_objects(db: Session, *, actor: AccessContext) -> list[dict[str, Any]]:
    scope = load_library_scope(db, actor=actor)
    return [_object_payload(scope, item) for item in scope.objects]


def get_library_object_detail(
    db: Session,
    *,
    actor: AccessContext,
    object_id: int,
) -> dict[str, Any] | None:
    scope = load_library_scope(db, actor=actor)
    registry_object = next((item for item in scope.objects if item.id == object_id), None)
    if registry_object is None:
        return None
    return {
        "object": _object_payload(scope, registry_object),
        "details": _type_details(scope, registry_object),
        "releases": list_library_releases_from_scope(scope, object_id=object_id),
    }


def list_library_releases_from_scope(
    scope: LibraryScope,
    *,
    object_id: int,
) -> list[dict[str, Any]]:
    skill = scope.skills_by_object_id.get(object_id)
    versions = (
        {version.id: version for version in scope.versions_by_skill_id.get(skill.id, [])}
        if skill
        else {}
    )
    rows: list[dict[str, Any]] = []
    for release in scope.releases_by_object_id.get(object_id, []):
        exposure = next(iter(scope.exposures_by_release_id.get(release.id, [])), None)
        version = versions.get(release.skill_version_id)
        rows.append(
            {
                "release_id": release.id,
                "version": version.version if version is not None else None,
                "state": release.state,
                "ready_at": _iso_stamp(release.ready_at),
                "visibility": _visibility_payload(exposure),
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
    if not any(item.id == object_id for item in scope.objects):
        return None
    return list_library_releases_from_scope(scope, object_id=object_id)


def get_library_release_detail(
    db: Session,
    *,
    actor: AccessContext,
    object_id: int,
    release_id: int,
) -> dict[str, Any] | None:
    scope = load_library_scope(db, actor=actor)
    registry_object = next((item for item in scope.objects if item.id == object_id), None)
    if registry_object is None:
        return None
    skill = scope.skills_by_object_id.get(object_id)
    version_map = (
        {version.id: version for version in scope.versions_by_skill_id.get(skill.id, [])}
        if skill is not None
        else {}
    )
    release = next(
        (item for item in scope.releases_by_object_id.get(object_id, []) if item.id == release_id),
        None,
    )
    if release is None:
        return None
    version = version_map.get(release.skill_version_id)
    exposure = next(iter(scope.exposures_by_release_id.get(release.id, [])), None)
    artifact_rows = _build_release_artifact_rows(db, release=release)
    visibility_rows = _build_release_visibility_rows(scope, release=release)
    distribution_summary = _release_distribution_summary(
        scope,
        release=release,
        artifact_rows=artifact_rows,
        visibility_rows=visibility_rows,
    )
    return {
        "object": _object_payload(scope, registry_object),
        "release": {
            "id": release.id,
            "version": version.version if version is not None else f"release-{release.id}",
            "visibility": (
                exposure.audience_type
                if exposure is not None and exposure.audience_type
                else "private"
            ),
            "created_at": humanize_timestamp(_iso_stamp(release.created_at)),
            "ready_at": humanize_timestamp(_iso_stamp(release.ready_at)),
            "readiness_state": release.state or "unknown",
            "exposure_policy": _build_exposure_policy(),
            **distribution_summary,
        },
        "artifact_rows": artifact_rows,
        "visibility_rows": visibility_rows,
    }


def list_library_token_rows(
    db: Session,
    *,
    actor: AccessContext,
    lang: str,
    object_id: int | None = None,
) -> list[dict[str, Any]]:
    scope = load_library_scope(db, actor=actor)
    return _build_token_rows_from_scope(scope, lang=lang, object_id=object_id)


def list_library_token_activity_rows(
    db: Session,
    *,
    actor: AccessContext,
    lang: str,
) -> list[dict[str, Any]]:
    scope = load_library_scope(db, actor=actor)
    token_rows = _build_token_rows_from_scope(scope, lang=lang)
    return _build_token_activity_rows_from_token_rows(token_rows)


def list_library_share_rows(
    db: Session,
    *,
    actor: AccessContext,
    lang: str,
    object_id: int | None = None,
) -> list[dict[str, Any]]:
    scope = load_library_scope(db, actor=actor)
    return _build_share_rows_from_scope(scope, lang=lang, object_id=object_id)


def list_library_activity_rows(
    db: Session,
    *,
    actor: AccessContext,
) -> list[dict[str, Any]]:
    scope = load_library_scope(db, actor=actor)
    return _build_activity_rows_from_scope(scope)


def _page_shell(*, title: str, body: str) -> str:
    return (
        "<!doctype html>"
        "<html><head>"
        f"<meta charset='utf-8'><title>{escape(title)}</title>"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )


def render_library_index_html(items: list[dict[str, Any]], *, lang: str) -> str:
    heading = pick_lang(lang, "对象库", "Library")
    cards = []
    for item in items:
        href = with_lang(f"/library/{item['id']}", lang)
        cards.append(
            "<li>"
            f"<a href='{escape(href)}'>{escape(item['display_name'])}</a>"
            f" <span>{escape(item['kind_label'])}</span>"
            "</li>"
        )
    body = f"<main><h1>{escape(heading)}</h1><ul>{''.join(cards)}</ul></main>"
    return _page_shell(title=heading, body=body)


def render_library_object_html(detail: dict[str, Any], *, lang: str) -> str:
    heading = detail["object"]["display_name"]
    releases_label = pick_lang(lang, "发布版本", "Releases")
    links = []
    for release in detail["releases"]:
        href = with_lang(
            f"/library/{detail['object']['id']}/releases/{release['release_id']}",
            lang,
        )
        label = release.get("version") or f"Release {release['release_id']}"
        links.append(
            "<li>"
            f"<a href='{escape(href)}'>"
            f"{escape(label)}"
            "</a></li>"
        )
    body = (
        "<main>"
        f"<h1>{escape(heading)}</h1>"
        f"<p>{escape(detail['object']['summary'] or '')}</p>"
        f"<h2>{escape(releases_label)}</h2>"
        f"<ul>{''.join(links)}</ul>"
        "</main>"
    )
    return _page_shell(title=heading, body=body)


def render_library_release_html(
    detail: dict[str, Any],
    release_payload: dict[str, Any],
    *,
    lang: str,
) -> str:
    heading = pick_lang(lang, "发布详情", "Release")
    audience = release_payload["visibility"]["audience_type"] or "-"
    version = release_payload.get("version") or f"Release {release_payload['release_id']}"
    body = (
        "<main>"
        f"<h1>{escape(heading)}</h1>"
        f"<p>{escape(detail['object']['display_name'])}</p>"
        f"<p>{escape(version)}</p>"
        f"<p>{escape(audience)}</p>"
        "</main>"
    )
    return _page_shell(title=heading, body=body)
