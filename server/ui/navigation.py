from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.models import (
    AccessGrant,
    Artifact,
    Credential,
    Exposure,
    Principal,
    Release,
    ReviewCase,
    Skill,
    SkillDraft,
    SkillVersion,
)
from server.ui.auth_state import principal_label
from server.ui.formatting import (
    humanize_audience_type,
    humanize_identifier,
    humanize_install_mode,
    humanize_listing_mode,
    humanize_review_gate,
    humanize_status,
    humanize_timestamp,
    load_json_list,
    load_json_object,
)
from server.ui.i18n import pick_lang, with_lang


def group_by(items: list[object], key_name: str) -> dict[int, list[object]]:
    grouped: dict[int, list[object]] = {}
    for item in items:
        key = getattr(item, key_name, None)
        if key is None:
            continue
        grouped.setdefault(int(key), []).append(item)
    return grouped


def first_by_id(items: list[object]) -> dict[int, object]:
    return {int(item.id): item for item in items}


def load_registry_scope(
    db: Session, *, principal_id: int | None, include_all: bool
) -> dict[str, object]:
    skill_query = select(Skill).order_by(Skill.updated_at.desc(), Skill.id.desc())
    if not include_all and principal_id is not None:
        skill_query = skill_query.where(Skill.namespace_id == principal_id)
    skills = db.scalars(skill_query).all()
    skill_ids = [skill.id for skill in skills]

    drafts = []
    versions = []
    releases = []
    exposures = []
    review_cases = []
    grants = []
    credentials = []

    if skill_ids:
        drafts = db.scalars(
            select(SkillDraft)
            .where(SkillDraft.skill_id.in_(skill_ids))
            .order_by(SkillDraft.updated_at.desc(), SkillDraft.id.desc())
        ).all()
        versions = db.scalars(
            select(SkillVersion)
            .where(SkillVersion.skill_id.in_(skill_ids))
            .order_by(SkillVersion.created_at.desc(), SkillVersion.id.desc())
        ).all()

    version_ids = [version.id for version in versions]
    if version_ids:
        releases = db.scalars(
            select(Release)
            .where(Release.skill_version_id.in_(version_ids))
            .order_by(Release.created_at.desc(), Release.id.desc())
        ).all()

    release_ids = [release.id for release in releases]
    if release_ids:
        exposures = db.scalars(
            select(Exposure)
            .where(Exposure.release_id.in_(release_ids))
            .order_by(Exposure.id.desc())
        ).all()

    exposure_ids = [exposure.id for exposure in exposures]
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

    grant_ids = [grant.id for grant in grants]
    credential_query = select(Credential).order_by(
        Credential.created_at.desc(), Credential.id.desc()
    )
    if include_all:
        credentials = db.scalars(credential_query).all()
    elif principal_id is not None:
        if grant_ids:
            credentials = db.scalars(
                credential_query.where(
                    (Credential.principal_id == principal_id) | (Credential.grant_id.in_(grant_ids))
                )
            ).all()
        else:
            credentials = db.scalars(
                credential_query.where(Credential.principal_id == principal_id)
            ).all()

    principal_ids = {skill.namespace_id for skill in skills}
    principal_ids.update(
        credential.principal_id for credential in credentials if credential.principal_id is not None
    )
    principal_ids.update(
        grant.created_by_principal_id
        for grant in grants
        if grant.created_by_principal_id is not None
    )
    principals = []
    if principal_ids:
        principals = db.scalars(
            select(Principal)
            .where(Principal.id.in_(sorted(principal_ids)))
            .order_by(Principal.id.asc())
        ).all()

    artifacts = []
    if release_ids:
        artifacts = db.scalars(
            select(Artifact)
            .where(Artifact.release_id.in_(release_ids))
            .order_by(Artifact.created_at.desc(), Artifact.id.desc())
        ).all()

    return {
        "skills": skills,
        "drafts": drafts,
        "versions": versions,
        "releases": releases,
        "exposures": exposures,
        "review_cases": review_cases,
        "grants": grants,
        "credentials": credentials,
        "principals": principals,
        "artifacts": artifacts,
    }


def build_site_nav(*, home: bool, lang: str, variant: str = "console") -> list[dict[str, str]]:
    if home:
        return [
            {"href": "#start", "label": pick_lang(lang, "开始", "Home base")},
            {"href": "#handoff", "label": pick_lang(lang, "交接", "Handoff")},
            {"href": "#console", "label": pick_lang(lang, "维护台", "Console")},
        ]
    if variant == "library":
        return [
            {"href": with_lang("/", lang), "label": pick_lang(lang, "首页", "Home")},
            {"href": with_lang("/library", lang), "label": pick_lang(lang, "对象库", "Library")},
            {"href": with_lang("/access", lang), "label": pick_lang(lang, "访问", "Access")},
            {"href": with_lang("/shares", lang), "label": pick_lang(lang, "分享", "Shares")},
            {"href": with_lang("/activity", lang), "label": pick_lang(lang, "活动", "Activity")},
            {"href": with_lang("/settings", lang), "label": pick_lang(lang, "设置", "Settings")},
        ]
    return [
        {"href": with_lang("/", lang), "label": pick_lang(lang, "首页", "Home")},
        {"href": with_lang("/skills", lang), "label": pick_lang(lang, "技能", "Skills")},
        {"href": with_lang("/skills#drafts", lang), "label": pick_lang(lang, "草稿", "Drafts")},
        {"href": with_lang("/skills#releases", lang), "label": pick_lang(lang, "发布", "Releases")},
        {"href": with_lang("/skills#share", lang), "label": pick_lang(lang, "分享", "Share")},
        {"href": with_lang("/access/tokens", lang), "label": pick_lang(lang, "访问", "Access")},
        {"href": with_lang("/review-cases", lang), "label": pick_lang(lang, "审核", "Review")},
    ]


def build_skill_items(
    *,
    skills: list[object],
    principals_by_id: dict[int, object],
    drafts_by_skill: dict[int, list[object]],
    versions_by_skill: dict[int, list[object]],
    releases_by_version: dict[int, list[object]],
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    skill_items: list[dict[str, Any]] = []
    for skill in skills[:limit]:
        skill_versions = versions_by_skill.get(skill.id, [])
        release_count = sum(
            len(releases_by_version.get(version.id, [])) for version in skill_versions
        )
        skill_items.append(
            {
                "id": skill.id,
                "display_name": skill.display_name,
                "slug": skill.slug,
                "summary": skill.summary
                or pick_lang(lang, "尚未填写技能摘要。", "No skill summary yet."),
                "namespace": principal_label(principals_by_id.get(skill.namespace_id)),
                "default_visibility_profile": skill.default_visibility_profile or "-",
                "draft_count": len(drafts_by_skill.get(skill.id, [])),
                "version_count": len(skill_versions),
                "release_count": release_count,
                "updated_at": humanize_timestamp(skill.updated_at.isoformat()),
                "detail_href": with_lang(f"/skills/{skill.id}", lang),
            }
        )
    return skill_items


def build_draft_items(
    *,
    drafts: list[object],
    skills_by_id: dict[int, object],
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    draft_items: list[dict[str, Any]] = []
    for draft in drafts[:limit]:
        skill = skills_by_id.get(draft.skill_id)
        metadata = load_json_object(draft.metadata_json)
        draft_items.append(
            {
                "id": draft.id,
                "skill_name": skill.display_name if skill else f"Skill #{draft.skill_id}",
                "state": humanize_status(draft.state, lang),
                "content_ref": draft.content_ref or "-",
                "entrypoint": metadata.get("entrypoint") or "-",
                "updated_at": humanize_timestamp(draft.updated_at.isoformat()),
                "detail_href": with_lang(f"/drafts/{draft.id}", lang),
            }
        )
    return draft_items


def build_release_items(
    *,
    releases: list[object],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    exposures_by_release: dict[int, list[object]],
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    release_items: list[dict[str, Any]] = []
    for release in releases[:limit]:
        version = versions_by_id.get(release.skill_version_id)
        skill = skills_by_id.get(version.skill_id) if version else None
        release_items.append(
            {
                "id": release.id,
                "skill_name": skill.display_name
                if skill
                else f"Skill #{version.skill_id if version else '?'}",
                "version": version.version if version else "-",
                "state": humanize_status(release.state, lang),
                "ready_at": humanize_timestamp(release.ready_at),
                "exposure_count": len(exposures_by_release.get(release.id, [])),
                "detail_href": with_lang(f"/releases/{release.id}", lang),
                "share_href": with_lang(f"/releases/{release.id}/share", lang),
            }
        )
    return release_items


def build_share_items(
    *,
    exposures: list[object],
    releases_by_id: dict[int, object],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    review_cases_by_exposure: dict[int, list[object]],
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    share_items: list[dict[str, Any]] = []
    for exposure in exposures[:limit]:
        release = releases_by_id.get(exposure.release_id)
        version = versions_by_id.get(release.skill_version_id) if release else None
        skill = skills_by_id.get(version.skill_id) if version else None
        review_case = (review_cases_by_exposure.get(exposure.id) or [None])[0]
        share_items.append(
            {
                "id": exposure.id,
                "skill_name": skill.display_name if skill else "-",
                "release_id": exposure.release_id,
                "audience": humanize_audience_type(exposure.audience_type, lang),
                "listing_mode": humanize_listing_mode(exposure.listing_mode, lang),
                "install_mode": humanize_install_mode(exposure.install_mode, lang),
                "review_gate": humanize_review_gate(exposure.review_requirement, lang),
                "state": humanize_status(exposure.state, lang),
                "review_case_state": humanize_review_gate(
                    review_case.state if review_case else "none",
                    lang,
                ),
                "share_href": with_lang(f"/releases/{exposure.release_id}/share", lang),
            }
        )
    return share_items


def build_review_items(
    *,
    review_cases: list[object],
    exposures_by_id: dict[int, object],
    releases_by_id: dict[int, object],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    review_items: list[dict[str, Any]] = []
    for review_case in review_cases[:limit]:
        exposure = exposures_by_id.get(review_case.exposure_id)
        release = releases_by_id.get(exposure.release_id) if exposure else None
        version = versions_by_id.get(release.skill_version_id) if release else None
        skill = skills_by_id.get(version.skill_id) if version else None
        review_items.append(
            {
                "id": review_case.id,
                "skill_name": skill.display_name if skill else "-",
                "audience": humanize_audience_type(
                    exposure.audience_type if exposure else None, lang
                ),
                "mode": humanize_review_gate(review_case.mode, lang),
                "state": humanize_review_gate(review_case.state, lang),
                "opened_at": humanize_timestamp(review_case.opened_at.isoformat()),
                "review_href": with_lang("/review-cases", lang),
            }
        )
    return review_items


def build_skill_draft_rows(*, drafts: list[object], lang: str) -> list[dict[str, Any]]:
    return [
        {
            "id": draft.id,
            "state": humanize_status(draft.state, lang),
            "content_ref": draft.content_ref or "-",
            "updated_at": humanize_timestamp(draft.updated_at.isoformat()),
            "detail_href": with_lang(f"/drafts/{draft.id}", lang),
        }
        for draft in drafts
    ]


def build_skill_version_rows(
    *,
    versions: list[object],
    releases_by_version: dict[int, list[object]],
    lang: str,
) -> list[dict[str, Any]]:
    version_rows: list[dict[str, Any]] = []
    for version in versions:
        release = (releases_by_version.get(version.id) or [None])[0]
        version_rows.append(
            {
                "id": version.id,
                "version": version.version,
                "created_at": humanize_timestamp(version.created_at.isoformat()),
                "release_href": with_lang(f"/releases/{release.id}", lang) if release else "",
                "has_release": release is not None,
            }
        )
    return version_rows


def build_skill_release_rows(
    *,
    releases: list[object],
    versions_by_id: dict[int, object],
    lang: str,
) -> list[dict[str, Any]]:
    return [
        {
            "id": release.id,
            "version": (
                versions_by_id.get(release.skill_version_id).version
                if versions_by_id.get(release.skill_version_id)
                else "-"
            ),
            "state": humanize_status(release.state, lang),
            "ready_at": humanize_timestamp(release.ready_at),
            "detail_href": with_lang(f"/releases/{release.id}", lang),
            "share_href": with_lang(f"/releases/{release.id}/share", lang),
        }
        for release in releases
    ]


def build_skill_detail_payload(
    *,
    skill: object,
    principal_name: str,
    draft_rows: list[dict[str, Any]],
    version_rows: list[dict[str, Any]],
    release_rows: list[dict[str, Any]],
    lang: str,
) -> dict[str, Any]:
    return {
        "skill": {
            "id": skill.id,
            "display_name": skill.display_name,
            "slug": skill.slug,
            "summary": skill.summary or pick_lang(lang, "尚未填写摘要。", "No summary yet."),
            "namespace": principal_name,
            "default_visibility_profile": skill.default_visibility_profile or "-",
            "status": humanize_status(skill.status, lang),
            "updated_at": humanize_timestamp(skill.updated_at.isoformat()),
        },
        "draft_rows": draft_rows,
        "version_rows": version_rows,
        "release_rows": release_rows,
    }


def build_draft_detail_payload(
    *,
    draft: object,
    skill: object,
    base_version: object | None,
    metadata: dict[str, Any],
    lang: str,
) -> dict[str, Any]:
    return {
        "draft": {
            "id": draft.id,
            "skill_name": skill.display_name,
            "state": humanize_status(draft.state, lang),
            "state_raw": draft.state,
            "content_ref": draft.content_ref or "",
            "base_version": base_version.version if base_version else "-",
            "updated_at": humanize_timestamp(draft.updated_at.isoformat()),
            "metadata_pretty": json.dumps(metadata, ensure_ascii=False, indent=2)
            if metadata
            else "{}",
            "skill_href": with_lang(f"/skills/{skill.id}", lang),
        }
    }


def build_release_artifact_rows(*, artifacts: list[object]) -> list[dict[str, Any]]:
    return [
        {
            "id": artifact.id,
            "kind": humanize_identifier(artifact.kind),
            "sha256": artifact.sha256 or "-",
            "size_bytes": str(artifact.size_bytes),
            "storage_uri": artifact.storage_uri or "-",
        }
        for artifact in artifacts
    ]


def build_release_exposure_rows(
    *,
    exposures: list[object],
    release_id: int,
    lang: str,
) -> list[dict[str, Any]]:
    return [
        {
            "id": exposure.id,
            "audience": humanize_audience_type(exposure.audience_type, lang),
            "state": humanize_status(exposure.state, lang),
            "listing_mode": humanize_listing_mode(exposure.listing_mode, lang),
            "share_href": with_lang(f"/releases/{release_id}/share", lang),
        }
        for exposure in exposures
    ]


def _release_platform_compatibility(release: object) -> dict[str, Any]:
    try:
        return json.loads(release.platform_compatibility_json or "{}")
    except json.JSONDecodeError:
        return {}


def _build_exposure_policy() -> dict[str, dict[str, Any]]:
    return {
        "private": {
            "allowed_requested_review_modes": ["none"],
            "effective_requested_review_mode": "none",
            "effective_review_requirement": "none",
        },
        "authenticated": {
            "allowed_requested_review_modes": ["none"],
            "effective_requested_review_mode": "none",
            "effective_review_requirement": "none",
        },
        "grant": {
            "allowed_requested_review_modes": ["none", "advisory", "blocking"],
            "effective_requested_review_mode": None,
            "effective_review_requirement": None,
        },
        "public": {
            "allowed_requested_review_modes": ["blocking"],
            "effective_requested_review_mode": "blocking",
            "effective_review_requirement": "blocking",
        },
    }


def build_release_detail_payload(
    *,
    release: object,
    version: object,
    skill: object,
    artifact_rows: list[dict[str, Any]],
    exposure_rows: list[dict[str, Any]],
    lang: str,
) -> dict[str, Any]:
    platform_compatibility = _release_platform_compatibility(release)
    return {
        "release": {
            "id": release.id,
            "skill_name": skill.display_name,
            "version": version.version,
            "state": humanize_status(release.state, lang),
            "state_raw": release.state,
            "format_version": release.format_version,
            "ready_at": humanize_timestamp(release.ready_at),
            "created_at": humanize_timestamp(release.created_at.isoformat()),
            "skill_href": with_lang(f"/skills/{skill.id}", lang),
            "share_href": with_lang(f"/releases/{release.id}/share", lang),
            "platform_compatibility": platform_compatibility,
            "canonical_runtime_platform": (
                platform_compatibility.get("canonical_runtime_platform") or "openclaw"
            ),
            "canonical_runtime": platform_compatibility.get("canonical_runtime") or {},
            "blocking_platforms": platform_compatibility.get("blocking_platforms") or [],
            "verified_support": platform_compatibility.get("verified_support") or {},
            "historical_platforms": platform_compatibility.get("historical_platforms") or [],
        },
        "artifact_rows": artifact_rows,
        "exposure_rows": exposure_rows,
    }


def _derive_exposure_action_state(
    *,
    exposure: object,
    review_case_state: str,
) -> dict[str, object]:
    state = str(getattr(exposure, "state", "") or "").strip().lower()
    review_requirement = str(
        getattr(exposure, "review_requirement", "") or ""
    ).strip().lower()

    can_patch = state not in {"revoked", "rejected"}
    can_revoke = state in {"pending_policy", "review_open", "active"}

    if state in {"active", "revoked", "rejected"}:
        return {
            "can_activate": False,
            "can_revoke": can_revoke,
            "can_patch": can_patch,
            "activation_block_reason": "",
        }

    if review_requirement == "blocking":
        if review_case_state == "approved":
            return {
                "can_activate": True,
                "can_revoke": can_revoke,
                "can_patch": can_patch,
                "activation_block_reason": "",
            }
        block_reason = {
            "open": "blocking_review_open",
            "rejected": "blocking_review_rejected",
        }.get(review_case_state, "blocking_review_unapproved")
        return {
            "can_activate": False,
            "can_revoke": can_revoke,
            "can_patch": can_patch,
            "activation_block_reason": block_reason,
        }

    return {
        "can_activate": state in {"pending_policy", "review_open"},
        "can_revoke": can_revoke,
        "can_patch": can_patch,
        "activation_block_reason": "",
    }


def build_share_rows(
    *,
    exposures: list[object],
    review_cases_by_exposure: dict[int, list[object]],
    grants_by_exposure: dict[int, list[object]],
    lang: str,
) -> list[dict[str, Any]]:
    share_rows: list[dict[str, Any]] = []
    for exposure in exposures:
        review_case = (review_cases_by_exposure.get(exposure.id) or [None])[0]
        review_case_state = str(getattr(review_case, "state", None) or "none")
        policy_snapshot = load_json_object(
            getattr(exposure, "policy_snapshot_json", "{}") or "{}"
        )
        share_rows.append(
            {
                "id": exposure.id,
                "audience": humanize_audience_type(exposure.audience_type, lang),
                "audience_raw": exposure.audience_type,
                "listing_mode": humanize_listing_mode(exposure.listing_mode, lang),
                "listing_mode_raw": exposure.listing_mode,
                "install_mode": humanize_install_mode(exposure.install_mode, lang),
                "install_mode_raw": exposure.install_mode,
                "review_requirement": humanize_review_gate(exposure.review_requirement, lang),
                "review_requirement_raw": exposure.review_requirement,
                "review_case_state": humanize_review_gate(
                    review_case_state,
                    lang,
                ),
                "review_case_state_raw": review_case_state,
                "requested_review_mode_raw": str(
                    policy_snapshot.get("requested_review_mode") or "none"
                ),
                "grant_count": len(grants_by_exposure.get(exposure.id, [])),
                "state": humanize_status(exposure.state, lang),
                "state_raw": exposure.state,
                **_derive_exposure_action_state(
                    exposure=exposure,
                    review_case_state=review_case_state,
                ),
            }
        )
    return share_rows


def build_release_share_payload(
    *,
    release: object,
    version: object,
    skill: object,
    share_rows: list[dict[str, Any]],
    lang: str,
) -> dict[str, Any]:
    platform_compatibility = _release_platform_compatibility(release)
    return {
        "release": {
            "id": release.id,
            "skill_name": skill.display_name,
            "version": version.version,
            "detail_href": with_lang(f"/releases/{release.id}", lang),
            "platform_compatibility": platform_compatibility,
            "canonical_runtime_platform": (
                platform_compatibility.get("canonical_runtime_platform") or "openclaw"
            ),
            "canonical_runtime": platform_compatibility.get("canonical_runtime") or {},
            "blocking_platforms": platform_compatibility.get("blocking_platforms") or [],
            "verified_support": platform_compatibility.get("verified_support") or {},
            "historical_platforms": platform_compatibility.get("historical_platforms") or [],
            "exposure_policy": _build_exposure_policy(),
        },
        "share_rows": share_rows,
    }


def build_credential_rows(
    *,
    credentials: list[object],
    principals_by_id: dict[int, object],
    grants_by_id: dict[int, object],
    exposures_by_id: dict[int, object],
    releases_by_id: dict[int, object],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    credential_rows: list[dict[str, Any]] = []
    for credential in credentials[:limit]:
        grant = grants_by_id.get(credential.grant_id) if credential.grant_id else None
        exposure = exposures_by_id.get(grant.exposure_id) if grant else None
        release = releases_by_id.get(exposure.release_id) if exposure else None
        version = versions_by_id.get(release.skill_version_id) if release else None
        skill = skills_by_id.get(version.skill_id) if version else None
        credential_rows.append(
            {
                "id": credential.id,
                "type": humanize_identifier(credential.type),
                "principal": principal_label(principals_by_id.get(credential.principal_id)),
                "scopes": ", ".join(load_json_list(credential.scopes_json)) or "-",
                "grant_id": grant.id if grant else "-",
                "release_label": f"{skill.display_name} {version.version}"
                if skill and version
                else "-",
                "expires_at": humanize_timestamp(credential.expires_at),
                "last_used_at": humanize_timestamp(credential.last_used_at),
            }
        )
    return credential_rows


def build_access_grant_rows(
    *,
    grants: list[object],
    exposures_by_id: dict[int, object],
    releases_by_id: dict[int, object],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    grant_rows: list[dict[str, Any]] = []
    for grant in grants[:limit]:
        exposure = exposures_by_id.get(grant.exposure_id)
        release = releases_by_id.get(exposure.release_id) if exposure else None
        version = versions_by_id.get(release.skill_version_id) if release else None
        skill = skills_by_id.get(version.skill_id) if version else None
        grant_rows.append(
            {
                "id": grant.id,
                "grant_type": humanize_identifier(grant.grant_type),
                "subject_ref": grant.subject_ref or "-",
                "state": humanize_status(grant.state, lang),
                "audience": humanize_audience_type(
                    exposure.audience_type if exposure else None, lang
                ),
                "release_label": f"{skill.display_name} {version.version}"
                if skill and version
                else "-",
            }
        )
    return grant_rows


def build_review_case_rows(
    *,
    review_cases: list[object],
    exposures_by_id: dict[int, object],
    releases_by_id: dict[int, object],
    versions_by_id: dict[int, object],
    skills_by_id: dict[int, object],
    lang: str,
    limit: int,
) -> list[dict[str, Any]]:
    review_rows: list[dict[str, Any]] = []
    for review_case in review_cases[:limit]:
        exposure = exposures_by_id.get(review_case.exposure_id)
        release = releases_by_id.get(exposure.release_id) if exposure else None
        version = versions_by_id.get(release.skill_version_id) if release else None
        skill = skills_by_id.get(version.skill_id) if version else None
        review_rows.append(
            {
                "id": review_case.id,
                "exposure_id": exposure.id if exposure else None,
                "skill_name": skill.display_name if skill else "-",
                "audience": humanize_audience_type(
                    exposure.audience_type if exposure else None, lang
                ),
                "mode": humanize_review_gate(review_case.mode, lang),
                "state": humanize_review_gate(review_case.state, lang),
                "state_raw": review_case.state,
                "opened_at": humanize_timestamp(review_case.opened_at.isoformat()),
                "closed_at": humanize_timestamp(review_case.closed_at),
                "share_href": with_lang(f"/releases/{release.id}/share", lang) if release else "",
            }
        )
    return review_rows


__all__ = [
    "build_access_grant_rows",
    "build_credential_rows",
    "build_draft_detail_payload",
    "build_draft_items",
    "build_release_artifact_rows",
    "build_release_detail_payload",
    "build_release_exposure_rows",
    "build_release_items",
    "build_release_share_payload",
    "build_review_case_rows",
    "build_review_items",
    "build_share_items",
    "build_share_rows",
    "build_site_nav",
    "build_skill_detail_payload",
    "build_skill_draft_rows",
    "build_skill_items",
    "build_skill_release_rows",
    "build_skill_version_rows",
    "first_by_id",
    "group_by",
    "load_registry_scope",
]
