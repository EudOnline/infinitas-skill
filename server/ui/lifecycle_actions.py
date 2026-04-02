from __future__ import annotations

from typing import Any

from server.ui.i18n import with_lang
from server.ui.navigation import (
    build_access_grant_rows,
    build_credential_rows,
    build_draft_items,
    build_release_artifact_rows,
    build_release_exposure_rows,
    build_release_items,
    build_review_case_rows,
    build_review_items,
    build_share_items,
    build_share_rows,
    build_skill_draft_rows,
    build_skill_items,
    build_skill_release_rows,
    build_skill_version_rows,
)


def build_skills_overview_actions(
    *,
    skills: list[object],
    drafts: list[object],
    versions: list[object],
    releases: list[object],
    exposures: list[object],
    review_cases: list[object],
    principals_by_id: dict[int, object],
    drafts_by_skill: dict[int, list[object]],
    versions_by_skill: dict[int, list[object]],
    releases_by_id: dict[int, object],
    releases_by_version: dict[int, list[object]],
    exposures_by_id: dict[int, object],
    exposures_by_release: dict[int, list[object]],
    review_cases_by_exposure: dict[int, list[object]],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    lang: str,
    limit: int,
) -> dict[str, Any]:
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
        drafts=drafts,
        skills_by_id=skills_by_id,
        lang=lang,
        limit=limit,
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
    return {
        "skill_items": skill_items,
        "draft_items": draft_items,
        "release_items": release_items,
        "share_items": share_items,
        "review_items": review_items,
        "access_href": with_lang("/access/tokens", lang),
        "review_cases_href": with_lang("/review-cases", lang),
    }


def build_skill_detail_rows_bundle(
    *,
    drafts: list[object],
    versions: list[object],
    releases: list[object],
    releases_by_version: dict[int, list[object]],
    versions_by_id: dict[int, object],
    lang: str,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "draft_rows": build_skill_draft_rows(drafts=drafts, lang=lang),
        "version_rows": build_skill_version_rows(
            versions=versions,
            releases_by_version=releases_by_version,
            lang=lang,
        ),
        "release_rows": build_skill_release_rows(
            releases=releases,
            versions_by_id=versions_by_id,
            lang=lang,
        ),
    }


def build_release_detail_rows_bundle(
    *,
    artifacts: list[object],
    exposures: list[object],
    release_id: int,
    lang: str,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "artifact_rows": build_release_artifact_rows(artifacts=artifacts),
        "exposure_rows": build_release_exposure_rows(
            exposures=exposures,
            release_id=release_id,
            lang=lang,
        ),
    }


def build_release_share_rows_bundle(
    *,
    exposures: list[object],
    review_cases_by_exposure: dict[int, list[object]],
    grants_by_exposure: dict[int, list[object]],
    lang: str,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "share_rows": build_share_rows(
            exposures=exposures,
            review_cases_by_exposure=review_cases_by_exposure,
            grants_by_exposure=grants_by_exposure,
            lang=lang,
        )
    }


def build_access_tokens_rows_bundle(
    *,
    credentials: list[object],
    grants: list[object],
    principals_by_id: dict[int, object],
    grants_by_id: dict[int, object],
    exposures_by_id: dict[int, object],
    releases_by_id: dict[int, object],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    lang: str,
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "credential_rows": build_credential_rows(
            credentials=credentials,
            principals_by_id=principals_by_id,
            grants_by_id=grants_by_id,
            exposures_by_id=exposures_by_id,
            releases_by_id=releases_by_id,
            versions_by_id=versions_by_id,
            skills_by_id=skills_by_id,
            lang=lang,
            limit=limit,
        ),
        "grant_rows": build_access_grant_rows(
            grants=grants,
            exposures_by_id=exposures_by_id,
            releases_by_id=releases_by_id,
            versions_by_id=versions_by_id,
            skills_by_id=skills_by_id,
            lang=lang,
            limit=limit,
        ),
    }


def build_review_cases_rows_bundle(
    *,
    review_cases: list[object],
    exposures_by_id: dict[int, object],
    releases_by_id: dict[int, object],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    lang: str,
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "review_rows": build_review_case_rows(
            review_cases=review_cases,
            exposures_by_id=exposures_by_id,
            releases_by_id=releases_by_id,
            versions_by_id=versions_by_id,
            skills_by_id=skills_by_id,
            lang=lang,
            limit=limit,
        )
    }


__all__ = [
    "build_access_tokens_rows_bundle",
    "build_release_detail_rows_bundle",
    "build_release_share_rows_bundle",
    "build_review_cases_rows_bundle",
    "build_skill_detail_rows_bundle",
    "build_skills_overview_actions",
]
