from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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


def group_by(items: list[object], key_name: str) -> dict[int, list[object]]:
    grouped: dict[int, list[object]] = {}
    for item in items:
        key = getattr(item, key_name, None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(item)
    return grouped


def iso_stamp(value) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def parse_datetime(value: object) -> datetime | None:
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


def iter_object_release_rows(scope: LibraryScope):
    for registry_object in scope.objects:
        skill = scope.skills_by_object_id.get(registry_object.id)
        version_map = (
            {version.id: version for version in scope.versions_by_skill_id.get(skill.id, [])}
            if skill is not None
            else {}
        )
        for release in scope.releases_by_object_id.get(registry_object.id, []):
            yield registry_object, release, version_map.get(release.skill_version_id)


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
    versions_by_skill_id = group_by(versions, "skill_id")

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
    exposures_by_release_id = group_by(exposures, "release_id")

    exposure_ids = [exposure.id for exposure in exposures]
    review_cases = []
    if exposure_ids:
        review_cases = db.scalars(
            select(ReviewCase)
            .where(ReviewCase.exposure_id.in_(exposure_ids))
            .order_by(ReviewCase.id.desc())
        ).all()
    review_cases_by_exposure_id = group_by(review_cases, "exposure_id")

    grants = []
    if exposure_ids:
        grants = db.scalars(
            select(AccessGrant)
            .where(AccessGrant.exposure_id.in_(exposure_ids))
            .order_by(AccessGrant.id.desc())
        ).all()
    grants_by_exposure_id = group_by(grants, "exposure_id")

    grant_ids = [grant.id for grant in grants]
    credentials = []
    if grant_ids:
        credentials = db.scalars(
            select(Credential)
            .where(Credential.grant_id.in_(grant_ids))
            .order_by(Credential.id.desc())
        ).all()
    credentials_by_grant_id = group_by(credentials, "grant_id")

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
