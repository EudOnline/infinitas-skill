from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from server.db import get_db
from server.modules.identity.auth import maybe_get_current_user
from server.ui.context import build_login_context, templates_for
from server.ui.home import build_home_context
from server.ui.session_bootstrap import build_session_bootstrap

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    session_user = maybe_get_current_user(request, db)
    context: dict[str, Any] = {"request": request}
    context.update(build_home_context(settings=request.app.state.settings, db=db, request=request))
    context["session_ui"] = build_session_bootstrap(context.get("session_ui"), session_user)
    context["page_mode"] = "home"
    context["show_console_session"] = False
    return templates_for(request).TemplateResponse(request, "index-kawaii.html", context)


@router.get("/login", response_class=HTMLResponse)
def login(request: Request) -> HTMLResponse:
    return templates_for(request).TemplateResponse(
        request, "login-kawaii.html", build_login_context(request)
    )
