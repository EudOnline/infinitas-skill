from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from server import __version__ as server_version
from server.auth import maybe_get_current_user
from server.db import get_db
from server.models import User
from server.ui.auth_state import (
    is_owner,
    require_draft_bundle_or_404,
    require_lifecycle_actor,
    require_release_bundle_or_404,
    require_skill_or_404,
)
from server.ui.console import build_console_forbidden_context
from server.ui.formatting import build_kawaii_ui_context
from server.ui.home import build_home_context
from server.ui.i18n import build_registry_base_url, pick_lang, resolve_language, with_lang
from server.ui.library import (
    get_library_object_detail,
    get_library_release_detail,
    list_library_activity_rows,
    list_library_objects,
    list_library_share_rows,
    list_library_token_activity_rows,
    list_library_token_rows,
)
from server.ui.lifecycle import (
    build_access_tokens_page_context,
    build_draft_detail_page_context,
    build_release_detail_page_context,
    build_release_share_page_context,
    build_review_cases_page_context,
    build_skill_detail_page_context,
    build_skills_page_context,
)
from server.ui.navigation import build_site_nav
from server.ui.session_bootstrap import build_session_bootstrap


def _blocked_actor_response(
    templates: Jinja2Templates,
    request: Request,
    actor: object,
):
    if isinstance(actor, RedirectResponse):
        return actor
    if isinstance(actor, dict):
        return templates.TemplateResponse(request, "console-forbidden.html", actor, status_code=403)
    return None


def _forbidden_owner_response(
    templates: Jinja2Templates,
    request: Request,
    user: User,
):
    context = build_console_forbidden_context(
        request=request,
        user=user,
        allowed_roles=("maintainer", "contributor"),
    )
    return templates.TemplateResponse(request, "console-forbidden.html", context, status_code=403)


def _build_login_context(request: Request) -> dict[str, Any]:
    lang = resolve_language(request)
    registry_base_url = build_registry_base_url(request)
    page_eyebrow = pick_lang(lang, "管理员分发台", "Admin distribution")
    page_kicker = pick_lang(lang, "访问入口", "Access entry")
    content = pick_lang(
        lang,
        "使用管理员令牌进入对象库，并通过 API 或 CLI 管理分发。",
        "Use an admin token to open the Library and manage distribution via API or CLI.",
    )
    return {
        "request": request,
        "title": pick_lang(lang, "登录", "Login"),
        "content": content,
        "page_eyebrow": page_eyebrow,
        "page_kicker": page_kicker,
        "page_mode": "console",
        "show_console_session": False,
        "nav_links": build_site_nav(home=False, lang=lang, variant="library"),
        "cli_command": f'curl -H "Authorization: Bearer <token>" {registry_base_url}/api/v1/me',
        "page_stats": [
            {
                "value": pick_lang(lang, "Bearer Token", "Bearer Token"),
                "label": pick_lang(lang, "认证方式", "Auth scheme"),
                "detail": pick_lang(lang, "由控制台签发", "Issued by control plane"),
            },
            {
                "value": "/api/v1/me",
                "label": pick_lang(lang, "首个检查点", "First probe"),
                "detail": pick_lang(lang, "验证 token 是否生效", "Validate token works"),
            },
            {
                "value": "/library",
                "label": pick_lang(lang, "管理入口", "Admin entry"),
                "detail": pick_lang(
                    lang, "进入对象库与分发管理界面", "Open the Library and distribution admin"
                ),
            },
        ],
        **build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow),
    }


def register_ui_routes(app: FastAPI, templates: Jinja2Templates, settings) -> None:
    def _build_admin_context(
        request: Request,
        actor,
        *,
        title: str,
        content: str,
        page_kicker: str,
        page_eyebrow: str,
    ) -> dict[str, Any]:
        lang = resolve_language(request)
        context = {
            "request": request,
            "title": title,
            "content": content,
            "page_kicker": page_kicker,
            "page_eyebrow": page_eyebrow,
            "page_mode": "default",
            "home_href": with_lang("/", lang),
            "nav_links": build_site_nav(home=False, lang=lang, variant="library"),
            "show_console_session": False,
            "session_ui": build_session_bootstrap({}, actor.user),
        }
        context.update(build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow))
        return context

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request, db: Session = Depends(get_db)):
        session_user = maybe_get_current_user(request, db)
        context = {
            "request": request,
            "app_name": settings.app_name,
        }
        if session_user is not None:
            context["user_count"] = db.scalar(select(func.count()).select_from(User)) or 0
        context.update(build_home_context(settings=settings, db=db, request=request))
        context["session_ui"] = build_session_bootstrap(context.get("session_ui"), session_user)
        return templates.TemplateResponse(request, "index-kawaii.html", context)

    @app.get("/v2")
    def index_v2_redirect():
        return RedirectResponse(url="/", status_code=307)

    @app.get("/library", response_class=HTMLResponse)
    def library_page(
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        lang = resolve_language(request)
        items = list_library_objects(db, actor=actor)
        context = _build_admin_context(
            request,
            actor,
            title=pick_lang(lang, "对象库", "Library"),
            content=pick_lang(
                lang,
                "查看对象、发布版本、可见范围和访问分发。",
                "Inspect objects, releases, visibility, and access distribution.",
            ),
            page_kicker=pick_lang(lang, "管理", "Admin"),
            page_eyebrow=pick_lang(lang, "对象库", "Library"),
        )
        context["library_items"] = [
            {
                **item,
                "default_release": (
                    (item.get("current_release") or {}).get("version")
                    if item.get("current_release")
                    else None
                ),
                "current_visibility": (
                    (item.get("current_visibility") or {}).get("audience_type") or "private"
                ),
                "detail_href": with_lang(f"/library/{item['id']}", lang),
            }
            for item in items
        ]
        return templates.TemplateResponse(request, "library.html", context)

    @app.get("/library/{object_id}", response_class=HTMLResponse)
    def library_object_page(
        object_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        lang = resolve_language(request)
        detail = get_library_object_detail(db, actor=actor, object_id=object_id)
        if detail is None:
            return RedirectResponse(url=with_lang("/library", lang), status_code=303)
        context = _build_admin_context(
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
        context["library_href"] = with_lang("/library", lang)
        context["object"] = {
            **detail["object"],
            "current_visibility": (
                (detail["object"].get("current_visibility") or {}).get("audience_type") or "private"
            ),
        }
        context["release_items"] = [
            {
                "version": item.get("version") or f"release-{item['release_id']}",
                "visibility": (item.get("visibility") or {}).get("audience_type") or "private",
                "readiness_state": item.get("state") or "unknown",
                "created_at": item.get("ready_at") or "-",
                "detail_href": with_lang(
                    f"/library/{object_id}/releases/{item['release_id']}",
                    lang,
                ),
                "shares_href": with_lang("/shares", lang),
            }
            for item in detail["releases"]
        ]
        context["token_items"] = list_library_token_rows(
            db,
            actor=actor,
            lang=lang,
            object_id=object_id,
        )
        context["share_items"] = list_library_share_rows(
            db,
            actor=actor,
            lang=lang,
            object_id=object_id,
        )
        return templates.TemplateResponse(request, "object-detail.html", context)

    @app.get("/library/{object_id}/releases/{release_id}", response_class=HTMLResponse)
    def library_release_page(
        object_id: int,
        release_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        lang = resolve_language(request)
        release_detail = get_library_release_detail(
            db,
            actor=actor,
            object_id=object_id,
            release_id=release_id,
        )
        if release_detail is None:
            return RedirectResponse(url=with_lang("/library", lang), status_code=303)
        context = _build_admin_context(
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
            **release_detail["object"],
            "detail_href": with_lang(f"/library/{object_id}", lang),
            "shares_href": with_lang("/shares", lang),
            "access_href": with_lang("/access", lang),
        }
        context["release"] = {
            **release_detail["release"],
            "shares_href": with_lang("/shares", lang),
            "access_href": with_lang("/access", lang),
        }
        context["artifact_rows"] = release_detail["artifact_rows"]
        context["visibility_rows"] = release_detail["visibility_rows"]
        return templates.TemplateResponse(request, "release-detail-v2.html", context)

    @app.get("/access", response_class=HTMLResponse)
    def access_center_page(
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        lang = resolve_language(request)
        context = _build_admin_context(
            request,
            actor,
            title=pick_lang(lang, "访问中心", "Access Center"),
            content=pick_lang(
                lang,
                "给 agent 分发读取或发布 Token，并查看使用情况。",
                "Issue reader or publisher tokens for agents and inspect usage.",
            ),
            page_kicker=pick_lang(lang, "访问", "Access"),
            page_eyebrow=pick_lang(lang, "Token", "Token"),
        )
        context["token_items"] = list_library_token_rows(db, actor=actor, lang=lang)
        context["token_activity_items"] = list_library_token_activity_rows(
            db,
            actor=actor,
            lang=lang,
        )
        return templates.TemplateResponse(request, "access-center.html", context)

    @app.get("/shares", response_class=HTMLResponse)
    def shares_page(
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        lang = resolve_language(request)
        context = _build_admin_context(
            request,
            actor,
            title=pick_lang(lang, "分享链接", "Share Links"),
            content=pick_lang(
                lang,
                "管理无需 Token 即可访问指定发布版本的分享链接。",
                "Manage links that allow release access without a token.",
            ),
            page_kicker=pick_lang(lang, "分享", "Shares"),
            page_eyebrow=pick_lang(lang, "链接", "Links"),
        )
        context["share_items"] = list_library_share_rows(db, actor=actor, lang=lang)
        return templates.TemplateResponse(request, "shares.html", context)

    @app.get("/activity", response_class=HTMLResponse)
    def activity_page(
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        lang = resolve_language(request)
        context = _build_admin_context(
            request,
            actor,
            title=pick_lang(lang, "活动记录", "Activity"),
            content=pick_lang(
                lang,
                "查看对象、分享和访问相关的审计轨迹。",
                "Inspect the audit trail for objects, shares, and access.",
            ),
            page_kicker=pick_lang(lang, "活动", "Activity"),
            page_eyebrow=pick_lang(lang, "审计", "Audit"),
        )
        context["activity_items"] = list_library_activity_rows(db, actor=actor)
        return templates.TemplateResponse(request, "activity.html", context)

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        lang = resolve_language(request)
        context = _build_admin_context(
            request,
            actor,
            title=pick_lang(lang, "设置", "Settings"),
            content=pick_lang(
                lang,
                "查看管理员 Token 和环境使用说明。",
                "Review admin token and environment guidance.",
            ),
            page_kicker=pick_lang(lang, "设置", "Settings"),
            page_eyebrow=pick_lang(lang, "环境", "Environment"),
        )
        context["environment"] = settings.environment
        context["registry_version"] = server_version
        context["admin_token_env_name"] = "INFINITAS_REGISTRY_API_TOKEN"
        context["bootstrap_user_count"] = len(settings.bootstrap_users)
        context["registry_read_token_count"] = len(settings.registry_read_tokens)
        context["object_kinds"] = ["Skill", "Agent preset", "Agent code"]
        context["library_href"] = with_lang("/library", lang)
        context["access_href"] = with_lang("/access", lang)
        context["shares_href"] = with_lang("/shares", lang)
        context["activity_href"] = with_lang("/activity", lang)
        return templates.TemplateResponse(request, "settings.html", context)

    @app.get("/skills", response_class=HTMLResponse)
    def skills_page(
        request: Request,
        limit: int = Query(default=12, ge=1, le=50),
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        context = build_skills_page_context(request=request, db=db, actor=actor, limit=limit)
        return templates.TemplateResponse(request, "skills.html", context)

    @app.get("/skills/{skill_id}", response_class=HTMLResponse)
    def skill_detail_page(
        skill_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        skill = require_skill_or_404(db, skill_id)
        principal_id = actor.principal.id if actor.principal else None
        if not is_owner(actor.user, principal_id, skill.namespace_id):
            return _forbidden_owner_response(templates, request, actor.user)
        context = build_skill_detail_page_context(request=request, db=db, skill=skill)
        return templates.TemplateResponse(request, "skill-detail.html", context)

    @app.get("/drafts/{draft_id}", response_class=HTMLResponse)
    def draft_detail_page(
        draft_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        draft, skill = require_draft_bundle_or_404(db, draft_id)
        principal_id = actor.principal.id if actor.principal else None
        if not is_owner(actor.user, principal_id, skill.namespace_id):
            return _forbidden_owner_response(templates, request, actor.user)
        context = build_draft_detail_page_context(request=request, db=db, draft=draft, skill=skill)
        return templates.TemplateResponse(request, "draft-detail.html", context)

    @app.get("/releases/{release_id}", response_class=HTMLResponse)
    def release_detail_page(
        release_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        release, version, skill = require_release_bundle_or_404(db, release_id)
        principal_id = actor.principal.id if actor.principal else None
        if not is_owner(actor.user, principal_id, skill.namespace_id):
            return _forbidden_owner_response(templates, request, actor.user)
        context = build_release_detail_page_context(
            request=request,
            db=db,
            release=release,
            version=version,
            skill=skill,
        )
        return templates.TemplateResponse(request, "release-detail.html", context)

    @app.get("/releases/{release_id}/share", response_class=HTMLResponse)
    def release_share_page(
        release_id: int,
        request: Request,
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        release, version, skill = require_release_bundle_or_404(db, release_id)
        principal_id = actor.principal.id if actor.principal else None
        if not is_owner(actor.user, principal_id, skill.namespace_id):
            return _forbidden_owner_response(templates, request, actor.user)
        context = build_release_share_page_context(
            request=request,
            db=db,
            release=release,
            version=version,
            skill=skill,
        )
        return templates.TemplateResponse(request, "share-detail.html", context)

    @app.get("/access/tokens", response_class=HTMLResponse)
    def access_tokens_page(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        context = build_access_tokens_page_context(request=request, db=db, actor=actor, limit=limit)
        return templates.TemplateResponse(request, "access-tokens.html", context)

    @app.get("/review-cases", response_class=HTMLResponse)
    def review_cases_page(
        request: Request,
        limit: int = Query(default=20, ge=1, le=100),
        db: Session = Depends(get_db),
    ):
        actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
        blocked = _blocked_actor_response(templates, request, actor)
        if blocked is not None:
            return blocked
        context = build_review_cases_page_context(request=request, db=db, actor=actor, limit=limit)
        return templates.TemplateResponse(request, "review-cases.html", context)

    @app.get("/login", response_class=HTMLResponse)
    def login(request: Request):
        return templates.TemplateResponse(request, "login-kawaii.html", _build_login_context(request))


__all__ = ["register_ui_routes"]
