from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import (
    AccessGrant,
    Credential,
    Exposure,
    Principal,
    Release,
    ReviewCase,
    Skill,
    SkillVersion,
)
from server.modules.access.authn import AccessContext


@dataclass(frozen=True)
class LibraryScope:
    skills: list[Skill]
    principals_by_id: dict[int, Principal]
    versions_by_skill_id: dict[int, list[SkillVersion]]
    releases_by_skill_id: dict[int, list[Release]]
    exposures_by_release_id: dict[int, list[Exposure]]
    review_cases_by_exposure_id: dict[int, list[ReviewCase]]
    grants_by_exposure_id: dict[int, list[AccessGrant]]
    credentials_by_grant_id: dict[int, list[Credential]]


def group_by(items: list[object], key_name: str) -> dict[int, list[object]]:
    grouped: dict[int, list[object]] = {}
    for item in items:
        key = getattr(item, key_name, None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(item)
    return grouped


def iso_stamp(value) -> str | None:
    from server.modules.shared.formatting import iso_format

    return iso_format(value)


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


def iter_skill_release_rows(scope: LibraryScope):
    for skill in scope.skills:
        version_map = {
            version.id: version for version in scope.versions_by_skill_id.get(skill.id, [])
        }
        for release in scope.releases_by_skill_id.get(skill.id, []):
            yield skill, release, version_map.get(release.skill_version_id)


def _scope_filter_for_actor(query, *, actor: AccessContext):
    if actor.user is not None and actor.user.role == "maintainer":
        return query
    principal_id = actor.principal.id if actor.principal is not None else None
    if principal_id is None:
        return query.where(Skill.id < 0)
    return query.where(Skill.namespace_id == principal_id)


def load_library_scope(db: Session, *, actor: AccessContext) -> LibraryScope:
    skill_query = select(Skill).order_by(
        Skill.updated_at.desc(),
        Skill.id.desc(),
    )
    skills = db.scalars(_scope_filter_for_actor(skill_query, actor=actor)).all()
    skill_ids = [item.id for item in skills]
    principal_ids = sorted({item.namespace_id for item in skills})

    principals = []
    if principal_ids:
        principals = db.scalars(
            select(Principal)
            .where(Principal.id.in_(principal_ids))
            .order_by(Principal.id.asc())
        ).all()

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
    if version_ids:
        releases = db.scalars(
            select(Release)
            .where(Release.skill_version_id.in_(version_ids))
            .order_by(Release.created_at.desc(), Release.id.desc())
        ).all()

    releases_by_skill_id: dict[int, list[Release]] = {}
    for release in releases:
        version = next((v for v in versions if v.id == release.skill_version_id), None)
        if version is not None:
            releases_by_skill_id.setdefault(int(version.skill_id), []).append(release)

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

    return LibraryScope(
        skills=skills,
        principals_by_id={principal.id: principal for principal in principals},
        versions_by_skill_id=versions_by_skill_id,
        releases_by_skill_id=releases_by_skill_id,
        exposures_by_release_id=exposures_by_release_id,
        review_cases_by_exposure_id=review_cases_by_exposure_id,
        grants_by_exposure_id=grants_by_exposure_id,
        credentials_by_grant_id=credentials_by_grant_id,
    )
