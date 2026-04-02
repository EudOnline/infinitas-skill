from __future__ import annotations

from typing import Any

from server.ui.navigation import (
    build_draft_detail_payload,
    build_release_detail_payload,
    build_release_share_payload,
    build_skill_detail_payload,
)


def build_skill_detail_state(
    *,
    skill: object,
    principal_name: str,
    draft_rows: list[dict[str, Any]],
    version_rows: list[dict[str, Any]],
    release_rows: list[dict[str, Any]],
    lang: str,
) -> dict[str, Any]:
    return build_skill_detail_payload(
        skill=skill,
        principal_name=principal_name,
        draft_rows=draft_rows,
        version_rows=version_rows,
        release_rows=release_rows,
        lang=lang,
    )


def build_draft_detail_state(
    *,
    draft: object,
    skill: object,
    base_version: object | None,
    metadata: dict[str, Any],
    lang: str,
) -> dict[str, Any]:
    return build_draft_detail_payload(
        draft=draft,
        skill=skill,
        base_version=base_version,
        metadata=metadata,
        lang=lang,
    )


def build_release_detail_state(
    *,
    release: object,
    version: object,
    skill: object,
    artifact_rows: list[dict[str, Any]],
    exposure_rows: list[dict[str, Any]],
    lang: str,
) -> dict[str, Any]:
    return build_release_detail_payload(
        release=release,
        version=version,
        skill=skill,
        artifact_rows=artifact_rows,
        exposure_rows=exposure_rows,
        lang=lang,
    )


def build_release_share_state(
    *,
    release: object,
    version: object,
    skill: object,
    share_rows: list[dict[str, Any]],
    lang: str,
) -> dict[str, Any]:
    return build_release_share_payload(
        release=release,
        version=version,
        skill=skill,
        share_rows=share_rows,
        lang=lang,
    )


def build_access_tokens_state(
    *,
    credential_rows: list[dict[str, Any]],
    grant_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "credential_rows": credential_rows,
        "grant_rows": grant_rows,
    }


def build_review_cases_state(*, review_rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"review_rows": review_rows}


__all__ = [
    "build_access_tokens_state",
    "build_draft_detail_state",
    "build_release_detail_state",
    "build_release_share_state",
    "build_review_cases_state",
    "build_skill_detail_state",
]
