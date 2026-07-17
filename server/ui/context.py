from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from server.i18n import build_registry_base_url, pick_lang, resolve_language, with_lang
from server.modules.access.authn import AccessContext
from server.ui.formatting import build_kawaii_ui_context
from server.ui.navigation import build_site_nav
from server.ui.session_bootstrap import build_session_bootstrap


def templates_for(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def blocked_actor_response(request: Request, actor: object) -> Response | None:
    if isinstance(actor, RedirectResponse):
        return actor
    if isinstance(actor, dict):
        return templates_for(request).TemplateResponse(
            request, "console-forbidden.html", actor, status_code=403
        )
    return None


def build_admin_context(
    request: Request,
    actor: AccessContext,
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
        "robots_noindex": True,
        "page_kicker": page_kicker,
        "page_eyebrow": page_eyebrow,
        "page_mode": "console",
        "home_href": with_lang("/", lang),
        "nav_links": build_site_nav(home=False, lang=lang),
        "show_console_session": True,
    }
    context.update(build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow))
    context["session_ui"] = build_session_bootstrap({}, actor.user)
    return context


def build_login_context(request: Request) -> dict[str, Any]:
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
        "robots_noindex": True,
        "nav_links": build_site_nav(home=False, lang=lang),
        "cli_command": (
            f'curl -H "Authorization: Bearer <token>" {registry_base_url}/api/v1/access/me'
        ),
        "page_stats": [],
        **build_kawaii_ui_context(request, lang, page_kicker, page_eyebrow),
    }
