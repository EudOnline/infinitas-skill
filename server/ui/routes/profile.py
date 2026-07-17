from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from server.db import get_db
from server.i18n import pick_lang, resolve_language
from server.modules.access.authn import AccessContext
from server.ui.auth_state import require_lifecycle_actor
from server.ui.context import blocked_actor_response, build_admin_context, templates_for

router = APIRouter()


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)) -> Response:
    actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
    blocked = blocked_actor_response(request, actor)
    if blocked is not None:
        return blocked
    actor = cast(AccessContext, actor)
    lang = resolve_language(request)
    context = build_admin_context(
        request,
        actor,
        title=pick_lang(lang, "档案", "Profile"),
        content=pick_lang(
            lang,
            "查看智能体档案与身份信息。",
            "View the agent archive and identity information.",
        ),
        page_kicker=pick_lang(lang, "档案", "Profile"),
        page_eyebrow=pick_lang(lang, "智能体档案", "Agent Archive"),
    )
    return templates_for(request).TemplateResponse(request, "profile.html", context)
