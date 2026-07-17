"""UI/API-neutral library queries and loaded scope."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypeVar

from sqlalchemy import DateTime, Select, func, select
from sqlalchemy.orm import Session

from server.modules.access.authn import AccessContext
from server.modules.access.models import AccessGrant
from server.modules.authoring.models import Skill, SkillVersion
from server.modules.exposure.models import Exposure
from server.modules.identity.models import Credential, Principal
from server.modules.release.models import Release
from server.modules.review.models import ReviewCase


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


T = TypeVar("T")


def group_by(items: Sequence[T], key_name: str) -> dict[int, list[T]]:
    grouped: dict[int, list[T]] = {}
    for item in items:
        key = getattr(item, key_name, None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(item)
    return grouped


def iso_stamp(value: DateTime | datetime | None) -> str | None:
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


def iter_skill_release_rows(
    scope: LibraryScope,
) -> Iterator[tuple[Skill, Release, SkillVersion | None]]:
    for skill in scope.skills:
        version_map = {
            version.id: version for version in scope.versions_by_skill_id.get(skill.id, [])
        }
        for release in scope.releases_by_skill_id.get(skill.id, []):
            yield skill, release, version_map.get(release.skill_version_id)


def iter_grant_credentials(
    scope: LibraryScope,
    *,
    object_id: int | None = None,
    grant_type: str | None = None,
) -> Iterator[tuple[Skill, Release, SkillVersion | None, Exposure, AccessGrant, Credential]]:
    """Yield (skill, release, version, exposure, grant, credential) tuples.

    Traverses the full skill -> release -> exposure -> grant -> credential
    chain, optionally filtered by object_id and grant_type.

    Args:
        scope: The library scope to traverse.
        object_id: If set, only yield entries for this skill ID.
        grant_type: If set, only yield grants matching this type
            (e.g. ``"link"`` for share links, ``None`` for tokens).
    """
    for skill, release, version in iter_skill_release_rows(scope):
        if object_id is not None and skill.id != object_id:
            continue
        for exposure in scope.exposures_by_release_id.get(release.id, []):
            for grant in scope.grants_by_exposure_id.get(exposure.id, []):
                if grant_type is not None and grant.grant_type != grant_type:
                    continue
                for credential in scope.credentials_by_grant_id.get(grant.id, []):
                    yield skill, release, version, exposure, grant, credential


def _scope_filter_for_actor(query: Select[Any], *, actor: AccessContext) -> Select[Any]:
    if actor.user is not None and actor.user.role == "maintainer":
        return query
    principal_id = actor.principal.id if actor.principal is not None else None
    if principal_id is None:
        return query.where(Skill.id < 0)
    return query.where(Skill.namespace_id == principal_id)


def _load_skills(
    db: Session,
    *,
    actor: AccessContext,
    skip: int,
    limit: int | None,
) -> tuple[list[Skill], int]:
    base_query = _scope_filter_for_actor(select(Skill), actor=actor)
    total = int(db.scalar(select(func.count()).select_from(base_query.subquery())) or 0)
    query = base_query.order_by(Skill.updated_at.desc(), Skill.id.desc())
    if skip > 0:
        query = query.offset(skip)
    if limit is not None:
        query = query.limit(limit)
    return list(db.scalars(query).all()), total


def _load_principals(db: Session, skills: list[Skill]) -> list[Principal]:
    principal_ids = sorted({item.namespace_id for item in skills})
    if not principal_ids:
        return []
    return list(
        db.scalars(
            select(Principal).where(Principal.id.in_(principal_ids)).order_by(Principal.id.asc())
        ).all()
    )


def _load_versions(db: Session, skill_ids: list[int]) -> list[SkillVersion]:
    if not skill_ids:
        return []
    return list(
        db.scalars(
            select(SkillVersion)
            .where(SkillVersion.skill_id.in_(skill_ids))
            .order_by(SkillVersion.created_at.desc(), SkillVersion.id.desc())
        ).all()
    )


def _load_releases(db: Session, versions: list[SkillVersion]) -> list[Release]:
    version_ids = [version.id for version in versions]
    if not version_ids:
        return []
    return list(
        db.scalars(
            select(Release)
            .where(Release.skill_version_id.in_(version_ids))
            .order_by(Release.created_at.desc(), Release.id.desc())
        ).all()
    )


def _group_releases_by_skill(
    releases: list[Release], versions: list[SkillVersion]
) -> dict[int, list[Release]]:
    skill_id_by_version = {version.id: int(version.skill_id) for version in versions}
    grouped: dict[int, list[Release]] = {}
    for release in releases:
        skill_id = skill_id_by_version.get(release.skill_version_id)
        if skill_id is not None:
            grouped.setdefault(skill_id, []).append(release)
    return grouped


def _load_exposures(db: Session, releases: list[Release]) -> list[Exposure]:
    release_ids = [release.id for release in releases]
    if not release_ids:
        return []
    return list(
        db.scalars(
            select(Exposure)
            .where(Exposure.release_id.in_(release_ids))
            .order_by(Exposure.id.desc())
        ).all()
    )


def _load_review_cases(db: Session, exposure_ids: list[int]) -> list[ReviewCase]:
    if not exposure_ids:
        return []
    return list(
        db.scalars(
            select(ReviewCase)
            .where(ReviewCase.exposure_id.in_(exposure_ids))
            .order_by(ReviewCase.id.desc())
        ).all()
    )


def _load_grants(db: Session, exposure_ids: list[int]) -> list[AccessGrant]:
    if not exposure_ids:
        return []
    return list(
        db.scalars(
            select(AccessGrant)
            .where(AccessGrant.exposure_id.in_(exposure_ids))
            .order_by(AccessGrant.id.desc())
        ).all()
    )


def _load_credentials(db: Session, grants: list[AccessGrant]) -> list[Credential]:
    grant_ids = [grant.id for grant in grants]
    if not grant_ids:
        return []
    return list(
        db.scalars(
            select(Credential)
            .where(Credential.grant_id.in_(grant_ids))
            .order_by(Credential.id.desc())
        ).all()
    )


def load_library_scope(
    db: Session,
    *,
    actor: AccessContext,
    skip: int = 0,
    limit: int | None = None,
) -> tuple[LibraryScope, int]:
    """Load library scope with optional pagination.

    Returns:
        Tuple of (LibraryScope, total_skill_count). When *skip*/*limit* are
        provided the scope contains only the requested page of skills, but
        *total_skill_count* reflects the full un-paginated count.
    """
    skills, total = _load_skills(db, actor=actor, skip=skip, limit=limit)
    skill_ids = [item.id for item in skills]
    principals = _load_principals(db, skills)
    versions = _load_versions(db, skill_ids)
    versions_by_skill_id = group_by(versions, "skill_id")
    releases = _load_releases(db, versions)
    releases_by_skill_id = _group_releases_by_skill(releases, versions)
    exposures = _load_exposures(db, releases)
    exposures_by_release_id = group_by(exposures, "release_id")
    exposure_ids = [exposure.id for exposure in exposures]
    review_cases = _load_review_cases(db, exposure_ids)
    review_cases_by_exposure_id = group_by(review_cases, "exposure_id")
    grants = _load_grants(db, exposure_ids)
    grants_by_exposure_id = group_by(grants, "exposure_id")
    credentials = _load_credentials(db, grants)
    credentials_by_grant_id = group_by(credentials, "grant_id")

    scope = LibraryScope(
        skills=skills,
        principals_by_id={principal.id: principal for principal in principals},
        versions_by_skill_id=versions_by_skill_id,
        releases_by_skill_id=releases_by_skill_id,
        exposures_by_release_id=exposures_by_release_id,
        review_cases_by_exposure_id=review_cases_by_exposure_id,
        grants_by_exposure_id=grants_by_exposure_id,
        credentials_by_grant_id=credentials_by_grant_id,
    )
    return scope, total
