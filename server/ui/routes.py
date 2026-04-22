from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
from server.ui.i18n import build_registry_base_url, pick_lang, resolve_language
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
    page_eyebrow = pick_lang(lang, "维护控制台", "Maintainer-only console")
    page_kicker = pick_lang(lang, "认证入口", "Auth entry")
    content = pick_lang(
        lang,
        "使用由托管控制台签发的 Bearer Token 调用 API 路由。",
        "Use a bearer token created by the hosted control plane to access API routes.",
    )
    return {
        "request": request,
        "title": pick_lang(lang, "登录", "Login"),
        "content": content,
        "page_eyebrow": page_eyebrow,
        "page_kicker": page_kicker,
        "page_mode": "console",
        "show_console_session": False,
        "nav_links": build_site_nav(home=False, lang=lang),
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
                "value": "/skills",
                "label": pick_lang(lang, "维护入口", "Maintainer entry"),
                "detail": pick_lang(
                    lang, "进入技能生命周期控制台", "Enter the skill lifecycle console"
                ),
            },
        ],
        **build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow),
    }


def register_ui_routes(app: FastAPI, templates: Jinja2Templates, settings) -> None:
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
