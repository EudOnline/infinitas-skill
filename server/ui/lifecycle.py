from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import (
    AccessGrant,
    Artifact,
    Exposure,
    Principal,
    Release,
    ReviewCase,
    Skill,
    SkillDraft,
    SkillVersion,
)
from server.modules.access.authn import AccessContext
from server.ui.auth_state import principal_label
from server.ui.console import build_lifecycle_console_context
from server.ui.formatting import load_json_object
from server.ui.i18n import resolve_language, with_lang
from server.ui.navigation import (
    build_access_grant_rows,
    build_credential_rows,
    build_draft_detail_payload,
    build_draft_items,
    build_release_artifact_rows,
    build_release_detail_payload,
    build_release_exposure_rows,
    build_release_items,
    build_release_share_payload,
    build_review_case_rows,
    build_review_items,
    build_share_items,
    build_share_rows,
    build_skill_detail_payload,
    build_skill_draft_rows,
    build_skill_items,
    build_skill_release_rows,
    build_skill_version_rows,
    first_by_id,
    group_by,
    load_registry_scope,
)
from server.ui.notifications import (
    describe_access_tokens_page,
    describe_draft_detail_page,
    describe_release_detail_page,
    describe_release_share_page,
    describe_review_cases_page,
    describe_skill_detail_page,
    describe_skills_page,
)


def build_skills_page_context(
    *,
    request: Request,
    db: Session,
    actor: AccessContext,
    limit: int,
) -> dict[str, Any]:
    lang = resolve_language(request)
    user = actor.user
    principal_id = actor.principal.id if actor.principal else None
    scope = load_registry_scope(
        db,
        principal_id=principal_id,
        include_all=user.role == "maintainer",
    )
    skills = scope["skills"]
    drafts = scope["drafts"]
    versions = scope["versions"]
    releases = scope["releases"]
    exposures = scope["exposures"]
    review_cases = scope["review_cases"]

    principals_by_id = first_by_id(scope["principals"])
    drafts_by_skill = group_by(drafts, "skill_id")
    versions_by_skill = group_by(versions, "skill_id")
    releases_by_id = first_by_id(releases)
    releases_by_version = group_by(releases, "skill_version_id")
    exposures_by_id = first_by_id(exposures)
    exposures_by_release = group_by(exposures, "release_id")
    review_cases_by_exposure = group_by(review_cases, "exposure_id")
    versions_by_id = first_by_id(versions)
    skills_by_id = first_by_id(skills)

    skill_items = build_skill_items(
        skills=skills,
        principals_by_id=principals_by_id,
        drafts_by_skill=drafts_by_skill,
        versions_by_skill=versions_by_skill,
        releases_by_version=releases_by_version,
        lang=lang,
        limit=limit,
    )
    draft_items = build_draft_items(
        drafts=drafts, skills_by_id=skills_by_id, lang=lang, limit=limit
    )
    release_items = build_release_items(
        releases=releases,
        versions_by_id=versions_by_id,
        skills_by_id=skills_by_id,
        exposures_by_release=exposures_by_release,
        lang=lang,
        limit=limit,
    )
    share_items = build_share_items(
        exposures=exposures,
        releases_by_id=releases_by_id,
        versions_by_id=versions_by_id,
        skills_by_id=skills_by_id,
        review_cases_by_exposure=review_cases_by_exposure,
        lang=lang,
        limit=limit,
    )
    review_items = build_review_items(
        review_cases=review_cases,
        exposures_by_id=exposures_by_id,
        releases_by_id=releases_by_id,
        versions_by_id=versions_by_id,
        skills_by_id=skills_by_id,
        lang=lang,
        limit=limit,
    )

    descriptor = describe_skills_page(
        lang,
        skills_count=len(skills),
        drafts_count=len(drafts),
        releases_count=len(releases),
        exposures_count=len(exposures),
        total_access_count=len(scope["credentials"]) + len(scope["grants"]),
        review_cases_count=len(review_cases),
    )
    context = build_lifecycle_console_context(
        request=request,
        title=descriptor["title"],
        content=descriptor["content"],
        limit=limit,
        items=skill_items,
        cli_command=descriptor["cli_command"],
        stats=descriptor["stats"],
    )
    context.update(
        {
            "skill_items": skill_items,
            "draft_items": draft_items,
            "release_items": release_items,
            "share_items": share_items,
            "review_items": review_items,
            "access_href": with_lang("/access/tokens", lang),
            "review_cases_href": with_lang("/review-cases", lang),
        }
    )
    return context


def build_skill_detail_page_context(
    *,
    request: Request,
    db: Session,
    skill: Skill,
) -> dict[str, Any]:
    lang = resolve_language(request)
    drafts = db.scalars(
        select(SkillDraft)
        .where(SkillDraft.skill_id == skill.id)
        .order_by(SkillDraft.updated_at.desc(), SkillDraft.id.desc())
    ).all()
    versions = db.scalars(
        select(SkillVersion)
        .where(SkillVersion.skill_id == skill.id)
        .order_by(SkillVersion.created_at.desc(), SkillVersion.id.desc())
    ).all()
    version_ids = [version.id for version in versions]
    releases = []
    if version_ids:
        releases = db.scalars(
            select(Release)
            .where(Release.skill_version_id.in_(version_ids))
            .order_by(Release.created_at.desc(), Release.id.desc())
        ).all()

    principal = db.get(Principal, skill.namespace_id)
    releases_by_version = group_by(releases, "skill_version_id")
    versions_by_id = first_by_id(versions)
    principal_name = principal_label(principal)

    draft_rows = build_skill_draft_rows(drafts=drafts, lang=lang)
    version_rows = build_skill_version_rows(
        versions=versions,
        releases_by_version=releases_by_version,
        lang=lang,
    )
    release_rows = build_skill_release_rows(
        releases=releases, versions_by_id=versions_by_id, lang=lang
    )

    descriptor = describe_skill_detail_page(
        lang,
        skill=skill,
        principal_name=principal_name,
        draft_count=len(drafts),
        release_count=len(releases),
    )
    context = build_lifecycle_console_context(
        request=request,
        title=descriptor["title"],
        content=descriptor["content"],
        limit=max(len(drafts), len(releases), 1),
        items=release_rows,
        cli_command=descriptor["cli_command"],
        stats=descriptor["stats"],
    )
    context.update(
        build_skill_detail_payload(
            skill=skill,
            principal_name=principal_name,
            draft_rows=draft_rows,
            version_rows=version_rows,
            release_rows=release_rows,
            lang=lang,
        )
    )
    return context


def build_draft_detail_page_context(
    *,
    request: Request,
    db: Session,
    draft: SkillDraft,
    skill: Skill,
) -> dict[str, Any]:
    lang = resolve_language(request)
    base_version = db.get(SkillVersion, draft.base_version_id) if draft.base_version_id else None
    metadata = load_json_object(draft.metadata_json)

    descriptor = describe_draft_detail_page(
        lang,
        draft=draft,
        base_version=base_version,
        skill_name=skill.display_name,
    )
    context = build_lifecycle_console_context(
        request=request,
        title=descriptor["title"],
        content=descriptor["content"],
        limit=1,
        items=[],
        cli_command=descriptor["cli_command"],
        stats=descriptor["stats"],
    )
    context.update(
        build_draft_detail_payload(
            draft=draft,
            skill=skill,
            base_version=base_version,
            metadata=metadata,
            lang=lang,
        )
    )
    return context


def build_release_detail_page_context(
    *,
    request: Request,
    db: Session,
    release: Release,
    version: SkillVersion,
    skill: Skill,
) -> dict[str, Any]:
    lang = resolve_language(request)
    artifacts = db.scalars(
        select(Artifact)
        .where(Artifact.release_id == release.id)
        .order_by(Artifact.kind.asc(), Artifact.id.asc())
    ).all()
    exposures = db.scalars(
        select(Exposure).where(Exposure.release_id == release.id).order_by(Exposure.id.desc())
    ).all()

    artifact_rows = build_release_artifact_rows(artifacts=artifacts)
    exposure_rows = build_release_exposure_rows(
        exposures=exposures, release_id=release.id, lang=lang
    )
    descriptor = describe_release_detail_page(
        lang,
        release=release,
        version=version,
        skill_name=skill.display_name,
        artifacts_count=len(artifacts),
        exposures_count=len(exposures),
    )
    context = build_lifecycle_console_context(
        request=request,
        title=descriptor["title"],
        content=descriptor["content"],
        limit=max(len(artifacts), len(exposures), 1),
        items=artifact_rows,
        cli_command=descriptor["cli_command"],
        stats=descriptor["stats"],
    )
    context.update(
        build_release_detail_payload(
            release=release,
            version=version,
            skill=skill,
            artifact_rows=artifact_rows,
            exposure_rows=exposure_rows,
            lang=lang,
        )
    )
    return context


def build_release_share_page_context(
    *,
    request: Request,
    db: Session,
    release: Release,
    version: SkillVersion,
    skill: Skill,
) -> dict[str, Any]:
    lang = resolve_language(request)
    exposures = db.scalars(
        select(Exposure).where(Exposure.release_id == release.id).order_by(Exposure.id.asc())
    ).all()
    exposure_ids = [exposure.id for exposure in exposures]
    review_cases = []
    grants = []
    if exposure_ids:
        review_cases = db.scalars(
            select(ReviewCase)
            .where(ReviewCase.exposure_id.in_(exposure_ids))
            .order_by(ReviewCase.id.desc())
        ).all()
        grants = db.scalars(
            select(AccessGrant)
            .where(AccessGrant.exposure_id.in_(exposure_ids))
            .order_by(AccessGrant.id.desc())
        ).all()

    share_rows = build_share_rows(
        exposures=exposures,
        review_cases_by_exposure=group_by(review_cases, "exposure_id"),
        grants_by_exposure=group_by(grants, "exposure_id"),
        lang=lang,
    )
    descriptor = describe_release_share_page(
        lang,
        release=release,
        version=version,
        skill_name=skill.display_name,
        exposures=exposures,
    )
    context = build_lifecycle_console_context(
        request=request,
        title=descriptor["title"],
        content=descriptor["content"],
        limit=max(len(share_rows), 1),
        items=share_rows,
        cli_command=descriptor["cli_command"],
        stats=descriptor["stats"],
    )
    context.update(
        build_release_share_payload(
            release=release,
            version=version,
            skill=skill,
            share_rows=share_rows,
            lang=lang,
        )
    )
    return context


def build_access_tokens_page_context(
    *,
    request: Request,
    db: Session,
    actor: AccessContext,
    limit: int,
) -> dict[str, Any]:
    lang = resolve_language(request)
    user = actor.user
    principal_id = actor.principal.id if actor.principal else None
    scope = load_registry_scope(
        db,
        principal_id=principal_id,
        include_all=user.role == "maintainer",
    )
    principals_by_id = first_by_id(scope["principals"])
    grants_by_id = first_by_id(scope["grants"])
    exposures_by_id = first_by_id(scope["exposures"])
    releases_by_id = first_by_id(scope["releases"])
    versions_by_id = first_by_id(scope["versions"])
    skills_by_id = first_by_id(scope["skills"])

    credential_rows = build_credential_rows(
        credentials=scope["credentials"],
        principals_by_id=principals_by_id,
        grants_by_id=grants_by_id,
        exposures_by_id=exposures_by_id,
        releases_by_id=releases_by_id,
        versions_by_id=versions_by_id,
        skills_by_id=skills_by_id,
        lang=lang,
        limit=limit,
    )
    grant_rows = build_access_grant_rows(
        grants=scope["grants"],
        exposures_by_id=exposures_by_id,
        releases_by_id=releases_by_id,
        versions_by_id=versions_by_id,
        skills_by_id=skills_by_id,
        lang=lang,
        limit=limit,
    )

    descriptor = describe_access_tokens_page(
        lang,
        credentials=scope["credentials"],
        grants=scope["grants"],
    )
    context = build_lifecycle_console_context(
        request=request,
        title=descriptor["title"],
        content=descriptor["content"],
        limit=limit,
        items=credential_rows,
        cli_command=descriptor["cli_command"],
        stats=descriptor["stats"],
    )
    context.update({"credential_rows": credential_rows, "grant_rows": grant_rows})
    return context


def build_review_cases_page_context(
    *,
    request: Request,
    db: Session,
    actor: AccessContext,
    limit: int,
) -> dict[str, Any]:
    lang = resolve_language(request)
    user = actor.user
    principal_id = actor.principal.id if actor.principal else None
    scope = load_registry_scope(
        db,
        principal_id=principal_id,
        include_all=user.role == "maintainer",
    )
    review_rows = build_review_case_rows(
        review_cases=scope["review_cases"],
        exposures_by_id=first_by_id(scope["exposures"]),
        releases_by_id=first_by_id(scope["releases"]),
        versions_by_id=first_by_id(scope["versions"]),
        skills_by_id=first_by_id(scope["skills"]),
        lang=lang,
        limit=limit,
    )

    descriptor = describe_review_cases_page(lang, review_cases=scope["review_cases"])
    context = build_lifecycle_console_context(
        request=request,
        title=descriptor["title"],
        content=descriptor["content"],
        limit=limit,
        items=review_rows,
        cli_command=descriptor["cli_command"],
        stats=descriptor["stats"],
    )
    context.update({"review_rows": review_rows})
    return context


__all__ = [
    "build_access_tokens_page_context",
    "build_draft_detail_page_context",
    "build_release_detail_page_context",
    "build_release_share_page_context",
    "build_review_cases_page_context",
    "build_skill_detail_page_context",
    "build_skills_page_context",
]
