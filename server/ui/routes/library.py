from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from server.db import get_db
from server.i18n import pick_lang, resolve_language, with_lang
from server.modules.access.authn import AccessContext
from server.modules.library.access import list_library_token_rows
from server.modules.library.objects import get_library_object_detail, list_library_objects
from server.modules.library.queries import load_library_scope
from server.modules.library.releases import get_library_release_detail
from server.modules.library.shares import list_library_share_rows
from server.ui.activity import list_activity_rows
from server.ui.auth_state import require_lifecycle_actor
from server.ui.context import blocked_actor_response, build_admin_context, templates_for

router = APIRouter()


def _actor(request: Request, db: Session) -> AccessContext | Response:
    actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
    blocked = blocked_actor_response(request, actor)
    return blocked if blocked is not None else cast(AccessContext, actor)


@router.get("/library/{object_id}", response_class=HTMLResponse)
def library_object_page(
    object_id: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    actor = _actor(request, db)
    if not isinstance(actor, AccessContext):
        return actor
    lang = resolve_language(request)
    scope, _total = load_library_scope(db, actor=actor)
    detail = get_library_object_detail(db, actor=actor, object_id=object_id, scope=scope)
    if detail is None:
        return RedirectResponse(url=with_lang("/manage", lang), status_code=303)
    context = build_admin_context(
        request,
        actor,
        title=detail["object"]["display_name"],
        content=pick_lang(
            lang,
            "查看对象概览、发布记录、访问和分享分发。",
            "Inspect overview, releases, access, and sharing for this object.",
        ),
        page_kicker=pick_lang(lang, "对象", "Object"),
        page_eyebrow=pick_lang(lang, "详情", "Detail"),
    )
    context["library_href"] = with_lang("/manage", lang)
    context["suppress_console_header"] = True
    context["object"] = {
        **detail["object"],
        "current_visibility": detail["object"]["current_visibility"]["audience_type"] or "private",
    }
    context["release_items"] = [
        {
            "version": item["version"] or f"release-{item['release_id']}",
            "visibility": item["visibility"]["audience_type"] or "private",
            "readiness_state": item["state"] or "unknown",
            "created_at": item["created_at"] or item["ready_at"] or "-",
            "detail_href": with_lang(f"/library/{object_id}/releases/{item['release_id']}", lang),
            "shares_href": with_lang("/manage#shares", lang),
        }
        for item in detail["releases"]
    ]
    context["token_items"] = list_library_token_rows(
        db, actor=actor, lang=lang, object_id=object_id, scope=scope
    )
    context["share_items"] = list_library_share_rows(
        db, actor=actor, lang=lang, object_id=object_id, scope=scope
    )
    return templates_for(request).TemplateResponse(request, "object-detail.html", context)


@router.get("/library/{object_id}/releases/{release_id}", response_class=HTMLResponse)
def library_release_page(
    object_id: int, release_id: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    actor = _actor(request, db)
    if not isinstance(actor, AccessContext):
        return actor
    lang = resolve_language(request)
    detail = get_library_release_detail(db, actor=actor, object_id=object_id, release_id=release_id)
    if detail is None:
        return RedirectResponse(url=with_lang("/manage", lang), status_code=303)
    context = build_admin_context(
        request,
        actor,
        title=pick_lang(lang, "发布详情", "Release"),
        content=pick_lang(
            lang,
            "查看当前发布的就绪状态、可见范围和产物摘要。",
            "Inspect readiness, visibility, and artifact summary for this release.",
        ),
        page_kicker=pick_lang(lang, "发布", "Release"),
        page_eyebrow=pick_lang(lang, "详情", "Detail"),
    )
    context["object"] = {
        **detail["object"],
        "detail_href": with_lang(f"/library/{object_id}", lang),
        "shares_href": with_lang("/manage#shares", lang),
        "access_href": with_lang("/manage#tokens", lang),
    }
    context["release"] = {
        **detail["release"],
        "shares_href": with_lang("/manage#shares", lang),
        "access_href": with_lang("/manage#tokens", lang),
    }
    context["suppress_console_header"] = True
    context["artifact_rows"] = detail["artifact_rows"]
    context["visibility_rows"] = detail["visibility_rows"]
    return templates_for(request).TemplateResponse(request, "release-detail-v2.html", context)


@router.get("/manage", response_class=HTMLResponse)
def manage_page(request: Request, db: Session = Depends(get_db)) -> Response:
    actor = _actor(request, db)
    if not isinstance(actor, AccessContext):
        return actor
    lang = resolve_language(request)
    scope, _total = load_library_scope(db, actor=actor)
    context = build_admin_context(
        request,
        actor,
        title=pick_lang(lang, "管理", "Management"),
        content=pick_lang(
            lang,
            "集中管理技能对象、访问令牌、分享链接和活动记录。",
            "Centrally manage skill objects, access tokens, share links, and activity.",
        ),
        page_kicker=pick_lang(lang, "管理", "Management"),
        page_eyebrow=pick_lang(lang, "技能与访问管理", "Skill & Access Management"),
    )
    context["object_items"], _total = list_library_objects(db, actor=actor, lang=lang)
    context["token_items"] = list_library_token_rows(db, actor=actor, lang=lang, scope=scope)
    context["share_items"] = list_library_share_rows(db, actor=actor, lang=lang, scope=scope)
    activity_owner_id = None
    if actor.user is None or actor.user.role != "maintainer":
        activity_owner_id = actor.principal.id if actor.principal is not None else 0
    context["activity_items"] = list_activity_rows(
        db,
        limit=50,
        owner_principal_id=activity_owner_id,
    )
    context["library_href"] = with_lang("/manage", lang)
    context["access_href"] = with_lang("/manage#tokens", lang)
    context["shares_href"] = with_lang("/manage#shares", lang)
    context["activity_href"] = with_lang("/manage#activity", lang)
    return templates_for(request).TemplateResponse(request, "manage.html", context)
