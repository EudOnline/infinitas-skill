from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import maybe_get_current_access_context
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
    User,
)
from server.modules.access.authn import AccessContext
from server.ui.console import build_console_forbidden_context, build_lifecycle_console_context
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
from server.ui.i18n import build_auth_redirect_url, pick_lang, resolve_language, with_lang


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


def principal_label(principal: Principal | None) -> str:
    if principal is None:
        return "-"
    return principal.display_name or principal.slug or f"principal-{principal.id}"


def is_owner(user: User, principal_id: int | None, resource_principal_id: int | None) -> bool:
    if user.role == "maintainer":
        return True
    if principal_id is None or resource_principal_id is None:
        return False
    return principal_id == resource_principal_id


def require_lifecycle_actor(
    request: Request,
    db: Session,
    *allowed_roles: str,
) -> AccessContext | RedirectResponse | dict[str, Any]:
    context = maybe_get_current_access_context(request, db)
    if context is None or context.user is None:
        return RedirectResponse(
            url=build_auth_redirect_url(request, resolve_language(request)),
            status_code=303,
        )
    if allowed_roles and context.user.role not in set(allowed_roles):
        return build_console_forbidden_context(
            request=request,
            user=context.user,
            allowed_roles=allowed_roles,
        )
    return context


def load_registry_scope(db: Session, *, principal_id: int | None, include_all: bool) -> dict[str, object]:
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
    credential_query = select(Credential).order_by(Credential.created_at.desc(), Credential.id.desc())
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
            credentials = db.scalars(credential_query.where(Credential.principal_id == principal_id)).all()

    principal_ids = {skill.namespace_id for skill in skills}
    principal_ids.update(
        credential.principal_id for credential in credentials if credential.principal_id is not None
    )
    principal_ids.update(
        grant.created_by_principal_id for grant in grants if grant.created_by_principal_id is not None
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
    releases_by_version = group_by(releases, "skill_version_id")
    exposures_by_release = group_by(exposures, "release_id")
    review_cases_by_exposure = group_by(review_cases, "exposure_id")
    versions_by_id = first_by_id(versions)
    skills_by_id = first_by_id(skills)

    skill_items = []
    for skill in skills[:limit]:
        skill_versions = versions_by_skill.get(skill.id, [])
        skill_releases = []
        for version in skill_versions:
            skill_releases.extend(releases_by_version.get(version.id, []))
        skill_items.append(
            {
                "id": skill.id,
                "display_name": skill.display_name,
                "slug": skill.slug,
                "summary": skill.summary or pick_lang(lang, "尚未填写技能摘要。", "No skill summary yet."),
                "namespace": principal_label(principals_by_id.get(skill.namespace_id)),
                "default_visibility_profile": skill.default_visibility_profile or "-",
                "draft_count": len(drafts_by_skill.get(skill.id, [])),
                "version_count": len(skill_versions),
                "release_count": len(skill_releases),
                "updated_at": humanize_timestamp(skill.updated_at.isoformat()),
                "detail_href": with_lang(f"/skills/{skill.id}", lang),
            }
        )

    draft_items = []
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

    release_items = []
    for release in releases[:limit]:
        version = versions_by_id.get(release.skill_version_id)
        skill = skills_by_id.get(version.skill_id) if version else None
        release_items.append(
            {
                "id": release.id,
                "skill_name": skill.display_name if skill else f"Skill #{version.skill_id if version else '?'}",
                "version": version.version if version else "-",
                "state": humanize_status(release.state, lang),
                "ready_at": humanize_timestamp(release.ready_at),
                "exposure_count": len(exposures_by_release.get(release.id, [])),
                "detail_href": with_lang(f"/releases/{release.id}", lang),
                "share_href": with_lang(f"/releases/{release.id}/share", lang),
            }
        )

    share_items = []
    for exposure in exposures[:limit]:
        release = next((item for item in releases if item.id == exposure.release_id), None)
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

    review_items = []
    for review_case in review_cases[:limit]:
        exposure = next((item for item in exposures if item.id == review_case.exposure_id), None)
        release = next((item for item in releases if item.id == exposure.release_id), None) if exposure else None
        version = versions_by_id.get(release.skill_version_id) if release else None
        skill = skills_by_id.get(version.skill_id) if version else None
        review_items.append(
            {
                "id": review_case.id,
                "skill_name": skill.display_name if skill else "-",
                "audience": humanize_audience_type(exposure.audience_type if exposure else None, lang),
                "mode": humanize_review_gate(review_case.mode, lang),
                "state": humanize_review_gate(review_case.state, lang),
                "opened_at": humanize_timestamp(review_case.opened_at.isoformat()),
                "review_href": with_lang("/review-cases", lang),
            }
        )

    total_credentials = int(len(scope["credentials"]))
    total_grants = int(len(scope["grants"]))
    context = build_lifecycle_console_context(
        request=request,
        title=pick_lang(lang, "技能生命周期", "Skill lifecycle"),
        content=pick_lang(
            lang,
            "用新的领域语言查看技能、草稿、发布、分享和审核状态，所有流转都收拢到同一套 private-first 生命周期里。",
            "Track skills, drafts, releases, sharing, and review with one private-first lifecycle vocabulary.",
        ),
        limit=limit,
        items=skill_items,
        cli_command="python scripts/registryctl.py --base-url https://skills.example.com --token <token> skills get <skill-id>",
        stats=[
            {"value": str(len(skills)), "label": pick_lang(lang, "技能", "Skills"), "detail": pick_lang(lang, "当前可见技能", "Visible skills")},
            {"value": str(len(drafts)), "label": pick_lang(lang, "草稿", "Drafts"), "detail": pick_lang(lang, "可继续编辑", "Still editable")},
            {"value": str(len(releases)), "label": pick_lang(lang, "发布", "Releases"), "detail": pick_lang(lang, "已生成 release", "Materialized releases")},
            {"value": str(len(exposures)), "label": pick_lang(lang, "分享", "Share"), "detail": pick_lang(lang, "暴露策略", "Exposure policies")},
            {"value": str(total_credentials + total_grants), "label": pick_lang(lang, "访问", "Access"), "detail": pick_lang(lang, "令牌与授权", "Tokens and grants")},
            {"value": str(len(review_cases)), "label": pick_lang(lang, "审核", "Review"), "detail": pick_lang(lang, "公开流转审核单", "Review cases for exposure")},
        ],
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
    versions_by_id = first_by_id(versions)
    principal = db.get(Principal, skill.namespace_id)

    draft_rows = [
        {
            "id": draft.id,
            "state": humanize_status(draft.state, lang),
            "content_ref": draft.content_ref or "-",
            "updated_at": humanize_timestamp(draft.updated_at.isoformat()),
            "detail_href": with_lang(f"/drafts/{draft.id}", lang),
        }
        for draft in drafts
    ]
    version_rows = [
        {
            "id": version.id,
            "version": version.version,
            "created_at": humanize_timestamp(version.created_at.isoformat()),
            "release_href": (
                with_lang(
                    f"/releases/{next((release.id for release in releases if release.skill_version_id == version.id), 0)}",
                    lang,
                )
                if any(release.skill_version_id == version.id for release in releases)
                else ""
            ),
        }
        for version in versions
    ]
    release_rows = [
        {
            "id": release.id,
            "version": versions_by_id.get(release.skill_version_id).version if versions_by_id.get(release.skill_version_id) else "-",
            "state": humanize_status(release.state, lang),
            "ready_at": humanize_timestamp(release.ready_at),
            "detail_href": with_lang(f"/releases/{release.id}", lang),
            "share_href": with_lang(f"/releases/{release.id}/share", lang),
        }
        for release in releases
    ]
    context = build_lifecycle_console_context(
        request=request,
        title=skill.display_name,
        content=pick_lang(
            lang,
            "这是技能命名空间下的单个技能视图，可直接追踪草稿、版本和发布状态。",
            "This skill detail view tracks drafts, versions, and releases inside one namespace.",
        ),
        limit=max(len(drafts), len(releases), 1),
        items=release_rows,
        cli_command=f"python scripts/registryctl.py --base-url https://skills.example.com --token <token> skills get {skill.id}",
        stats=[
            {"value": principal_label(principal), "label": pick_lang(lang, "命名空间", "Namespace"), "detail": skill.slug},
            {"value": str(len(drafts)), "label": pick_lang(lang, "草稿", "Drafts"), "detail": pick_lang(lang, "当前技能草稿", "Open drafts")},
            {"value": str(len(releases)), "label": pick_lang(lang, "发布", "Releases"), "detail": pick_lang(lang, "关联 release", "Linked releases")},
        ],
    )
    context.update(
        {
            "skill": {
                "id": skill.id,
                "display_name": skill.display_name,
                "slug": skill.slug,
                "summary": skill.summary or pick_lang(lang, "尚未填写摘要。", "No summary yet."),
                "namespace": principal_label(principal),
                "default_visibility_profile": skill.default_visibility_profile or "-",
                "status": humanize_status(skill.status, lang),
                "updated_at": humanize_timestamp(skill.updated_at.isoformat()),
            },
            "draft_rows": draft_rows,
            "version_rows": version_rows,
            "release_rows": release_rows,
        }
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
    context = build_lifecycle_console_context(
        request=request,
        title=pick_lang(lang, "草稿详情", "Draft detail"),
        content=pick_lang(
            lang,
            "草稿是可编辑工作区。这里展示内容引用、元数据快照以及后续封版关系。",
            "Drafts are editable workspaces. This view shows content refs, metadata snapshots, and the later sealed lineage.",
        ),
        limit=1,
        items=[],
        cli_command=f"python scripts/registryctl.py --base-url https://skills.example.com --token <token> drafts update {draft.id} --metadata-json '{{}}'",
        stats=[
            {"value": humanize_status(draft.state, lang), "label": pick_lang(lang, "状态", "State"), "detail": pick_lang(lang, "草稿当前状态", "Current draft state")},
            {"value": base_version.version if base_version else "-", "label": pick_lang(lang, "基线版本", "Base version"), "detail": pick_lang(lang, "可为空", "Optional")},
            {"value": humanize_timestamp(draft.updated_at.isoformat()), "label": pick_lang(lang, "更新时间", "Updated"), "detail": skill.display_name},
        ],
    )
    context.update(
        {
            "draft": {
                "id": draft.id,
                "skill_name": skill.display_name,
                "state": humanize_status(draft.state, lang),
                "content_ref": draft.content_ref or "-",
                "base_version": base_version.version if base_version else "-",
                "updated_at": humanize_timestamp(draft.updated_at.isoformat()),
                "metadata_pretty": json.dumps(metadata, ensure_ascii=False, indent=2) if metadata else "{}",
                "skill_href": with_lang(f"/skills/{skill.id}", lang),
            }
        }
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
        select(Exposure)
        .where(Exposure.release_id == release.id)
        .order_by(Exposure.id.desc())
    ).all()
    artifact_rows = [
        {
            "id": artifact.id,
            "kind": humanize_identifier(artifact.kind),
            "sha256": artifact.sha256 or "-",
            "size_bytes": str(artifact.size_bytes),
            "storage_uri": artifact.storage_uri or "-",
        }
        for artifact in artifacts
    ]
    exposure_rows = [
        {
            "id": exposure.id,
            "audience": humanize_audience_type(exposure.audience_type, lang),
            "state": humanize_status(exposure.state, lang),
            "listing_mode": humanize_listing_mode(exposure.listing_mode, lang),
            "share_href": with_lang(f"/releases/{release.id}/share", lang),
        }
        for exposure in exposures
    ]
    context = build_lifecycle_console_context(
        request=request,
        title=pick_lang(lang, "发布详情", "Release detail"),
        content=pick_lang(
            lang,
            "发布是不可变交付物。这里把产物、可见性和后续分享策略集中在一起。",
            "A release is the immutable delivery unit. This page groups artifacts, visibility, and downstream sharing state together.",
        ),
        limit=max(len(artifacts), len(exposures), 1),
        items=artifact_rows,
        cli_command=f"python scripts/registryctl.py --base-url https://skills.example.com --token <token> releases get {release.id}",
        stats=[
            {"value": skill.display_name, "label": pick_lang(lang, "技能", "Skill"), "detail": version.version},
            {"value": humanize_status(release.state, lang), "label": pick_lang(lang, "状态", "State"), "detail": pick_lang(lang, "release 生命周期", "Release lifecycle")},
            {"value": str(len(artifacts)), "label": pick_lang(lang, "产物", "Artifacts"), "detail": pick_lang(lang, "manifest / bundle / signature", "manifest / bundle / signature")},
            {"value": str(len(exposures)), "label": pick_lang(lang, "分享", "Share"), "detail": pick_lang(lang, "可见性出口", "Audience exits")},
        ],
    )
    context.update(
        {
            "release": {
                "id": release.id,
                "skill_name": skill.display_name,
                "version": version.version,
                "state": humanize_status(release.state, lang),
                "format_version": release.format_version,
                "ready_at": humanize_timestamp(release.ready_at),
                "created_at": humanize_timestamp(release.created_at.isoformat()),
                "skill_href": with_lang(f"/skills/{skill.id}", lang),
                "share_href": with_lang(f"/releases/{release.id}/share", lang),
            },
            "artifact_rows": artifact_rows,
            "exposure_rows": exposure_rows,
        }
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
        select(Exposure)
        .where(Exposure.release_id == release.id)
        .order_by(Exposure.id.asc())
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
    review_cases_by_exposure = group_by(review_cases, "exposure_id")
    grants_by_exposure = group_by(grants, "exposure_id")
    share_rows = []
    for exposure in exposures:
        review_case = (review_cases_by_exposure.get(exposure.id) or [None])[0]
        share_rows.append(
            {
                "id": exposure.id,
                "audience": humanize_audience_type(exposure.audience_type, lang),
                "listing_mode": humanize_listing_mode(exposure.listing_mode, lang),
                "install_mode": humanize_install_mode(exposure.install_mode, lang),
                "review_requirement": humanize_review_gate(exposure.review_requirement, lang),
                "review_case_state": humanize_review_gate(
                    review_case.state if review_case else "none",
                    lang,
                ),
                "grant_count": len(grants_by_exposure.get(exposure.id, [])),
                "state": humanize_status(exposure.state, lang),
            }
        )
    context = build_lifecycle_console_context(
        request=request,
        title=pick_lang(lang, "分享与可见性", "Share and visibility"),
        content=pick_lang(
            lang,
            "一个 release 可以同时拥有私人、令牌共享和公开三种出口。公开出口必须经过审核，私人出口可直接启用。",
            "A release can expose private, token-shared, and public audiences at the same time. Public audiences must pass review while private ones can activate directly.",
        ),
        limit=max(len(share_rows), 1),
        items=share_rows,
        cli_command=f"python scripts/registryctl.py --base-url https://skills.example.com --token <token> exposures create {release.id} --audience-type public",
        stats=[
            {"value": skill.display_name, "label": pick_lang(lang, "技能", "Skill"), "detail": version.version},
            {"value": str(sum(1 for item in exposures if item.audience_type == 'private')), "label": pick_lang(lang, "私人", "Private"), "detail": pick_lang(lang, "仅作者侧", "Author-side only")},
            {"value": str(sum(1 for item in exposures if item.audience_type == 'grant')), "label": pick_lang(lang, "令牌共享", "Shared by token"), "detail": pick_lang(lang, "细到 token", "Token-scoped access")},
            {"value": str(sum(1 for item in exposures if item.audience_type == 'public')), "label": pick_lang(lang, "公开", "Public"), "detail": pick_lang(lang, "匿名可见", "Anonymous install path")},
        ],
    )
    context.update(
        {
            "release": {
                "id": release.id,
                "skill_name": skill.display_name,
                "version": version.version,
                "detail_href": with_lang(f"/releases/{release.id}", lang),
            },
            "share_rows": share_rows,
        }
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

    credential_rows = []
    for credential in scope["credentials"][:limit]:
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
                "release_label": f"{skill.display_name} {version.version}" if skill and version else "-",
                "expires_at": humanize_timestamp(credential.expires_at),
                "last_used_at": humanize_timestamp(credential.last_used_at),
            }
        )

    grant_rows = []
    for grant in scope["grants"][:limit]:
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
                "audience": humanize_audience_type(exposure.audience_type if exposure else None, lang),
                "release_label": f"{skill.display_name} {version.version}" if skill and version else "-",
            }
        )

    context = build_lifecycle_console_context(
        request=request,
        title=pick_lang(lang, "访问令牌与授权", "Access tokens and grants"),
        content=pick_lang(
            lang,
            "这里同时展示个人 token 和 grant 绑定令牌。后续要做更细粒度权限，只需要在 grant / credential 层扩展，不必再改技能生命周期。",
            "This page groups personal tokens and grant-bound credentials. Finer permission models can grow inside grants and credentials without reshaping the skill lifecycle.",
        ),
        limit=limit,
        items=credential_rows,
        cli_command="python scripts/registryctl.py --base-url https://skills.example.com --token <token> tokens me",
        stats=[
            {"value": str(len(scope["credentials"])), "label": pick_lang(lang, "令牌", "Tokens"), "detail": pick_lang(lang, "当前可见 credential", "Visible credentials")},
            {"value": str(sum(1 for item in scope["credentials"] if item.type == "personal_token")), "label": pick_lang(lang, "个人", "Personal"), "detail": pick_lang(lang, "用户会话 token", "User session tokens")},
            {"value": str(sum(1 for item in scope["credentials"] if item.type == "grant_token")), "label": pick_lang(lang, "授权", "Grant"), "detail": pick_lang(lang, "共享 / 安装 token", "Shared install tokens")},
            {"value": str(len(scope["grants"])), "label": pick_lang(lang, "授权记录", "Grant records"), "detail": pick_lang(lang, "与 exposure 绑定", "Bound to exposures")},
        ],
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
    exposures_by_id = first_by_id(scope["exposures"])
    releases_by_id = first_by_id(scope["releases"])
    versions_by_id = first_by_id(scope["versions"])
    skills_by_id = first_by_id(scope["skills"])

    review_rows = []
    for review_case in scope["review_cases"][:limit]:
        exposure = exposures_by_id.get(review_case.exposure_id)
        release = releases_by_id.get(exposure.release_id) if exposure else None
        version = versions_by_id.get(release.skill_version_id) if release else None
        skill = skills_by_id.get(version.skill_id) if version else None
        review_rows.append(
            {
                "id": review_case.id,
                "skill_name": skill.display_name if skill else "-",
                "audience": humanize_audience_type(exposure.audience_type if exposure else None, lang),
                "mode": humanize_review_gate(review_case.mode, lang),
                "state": humanize_review_gate(review_case.state, lang),
                "opened_at": humanize_timestamp(review_case.opened_at.isoformat()),
                "closed_at": humanize_timestamp(review_case.closed_at),
            }
        )

    context = build_lifecycle_console_context(
        request=request,
        title=pick_lang(lang, "审核收件箱", "Review inbox"),
        content=pick_lang(
            lang,
            "公开技能必须经过审核。这个收件箱把公开 exposure 的审核需求和当前结论统一放在一起。",
            "Public skills must pass review. This inbox gathers review needs and current outcomes for public-facing exposures.",
        ),
        limit=limit,
        items=review_rows,
        cli_command="python scripts/registryctl.py --base-url https://skills.example.com --token <token> reviews get-case <review-case-id>",
        stats=[
            {"value": str(len(scope["review_cases"])), "label": pick_lang(lang, "总数", "Total"), "detail": pick_lang(lang, "当前可见 case", "Visible review cases")},
            {"value": str(sum(1 for item in scope["review_cases"] if item.state == "open")), "label": pick_lang(lang, "待处理", "Open"), "detail": pick_lang(lang, "仍待结论", "Still awaiting a decision")},
            {"value": str(sum(1 for item in scope["review_cases"] if item.state == "approved")), "label": pick_lang(lang, "已通过", "Approved"), "detail": pick_lang(lang, "可以公开", "Ready for public install")},
            {"value": str(sum(1 for item in scope["review_cases"] if item.state == "rejected")), "label": pick_lang(lang, "已拒绝", "Rejected"), "detail": pick_lang(lang, "需要回退策略", "Needs a fallback audience")},
        ],
    )
    context.update({"review_rows": review_rows})
    return context


def require_skill_or_404(db: Session, skill_id: int) -> Skill:
    skill = db.get(Skill, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return skill


def require_draft_bundle_or_404(db: Session, draft_id: int) -> tuple[SkillDraft, Skill]:
    draft = db.get(SkillDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="draft not found")
    skill = db.get(Skill, draft.skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return draft, skill


def require_release_bundle_or_404(db: Session, release_id: int) -> tuple[Release, SkillVersion, Skill]:
    release = db.get(Release, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="release not found")
    version = db.get(SkillVersion, release.skill_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="skill version not found")
    skill = db.get(Skill, version.skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="skill not found")
    return release, version, skill


__all__ = [
    "build_access_tokens_page_context",
    "build_draft_detail_page_context",
    "build_release_detail_page_context",
    "build_release_share_page_context",
    "build_review_cases_page_context",
    "build_skill_detail_page_context",
    "build_skills_page_context",
    "is_owner",
    "load_registry_scope",
    "principal_label",
    "require_draft_bundle_or_404",
    "require_lifecycle_actor",
    "require_release_bundle_or_404",
    "require_skill_or_404",
]
