from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from server import __version__ as server_version
from server.db import get_db
from server.i18n import pick_lang, resolve_language, with_lang
from server.modules.access.authn import AccessContext
from server.ui.auth_state import require_lifecycle_actor
from server.ui.context import blocked_actor_response, build_admin_context, templates_for

router = APIRouter()


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)) -> Response:
    actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
    blocked = blocked_actor_response(request, actor)
    if blocked is not None:
        return blocked
    actor = cast(AccessContext, actor)
    lang = resolve_language(request)
    settings = request.app.state.settings
    context = build_admin_context(
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
    context.update(
        environment=settings.environment,
        registry_version=server_version,
        admin_token_env_name="INFINITAS_REGISTRY_API_TOKEN",  # noqa: S106
        bootstrap_user_count=len(settings.bootstrap_users),
        registry_read_token_count=len(settings.registry_read_tokens),
        object_kinds=["Skill"],
        library_href=with_lang("/manage", lang),
        access_href=with_lang("/manage#tokens", lang),
        shares_href=with_lang("/manage#shares", lang),
        activity_href=with_lang("/manage#activity", lang),
    )
    return templates_for(request).TemplateResponse(request, "settings.html", context)
