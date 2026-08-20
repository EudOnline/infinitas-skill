from __future__ import annotations

from typing import Any, cast
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

import server.modules.identity.agent_service as agent_service
from server.db import get_db
from server.i18n import pick_lang, resolve_language
from server.modules.access.authn import AccessContext
from server.modules.identity.agent_schemas import AgentInvitationCreateRequest
from server.modules.identity.guards import require_user_role
from server.ui.auth_state import require_lifecycle_actor
from server.ui.context import blocked_actor_response, build_admin_context, templates_for

router = APIRouter()


async def _form(request: Request) -> dict[str, str]:
    raw = await request.body()
    values = parse_qs(raw.decode("utf-8"), keep_blank_values=True)
    return {key: items[-1] for key, items in values.items() if items}


def _maintainer(request: Request, db: Session) -> tuple[Any, Any]:
    actor = require_lifecycle_actor(request, db, "maintainer")
    blocked = blocked_actor_response(request, actor)
    if blocked is not None:
        return blocked, None
    context = cast(AccessContext, actor)
    require_user_role(context, roles={"maintainer"})
    return None, actor


@router.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request, db: Session = Depends(get_db)) -> Response:
    blocked, actor = _maintainer(request, db)
    if blocked is not None:
        return blocked
    assert actor is not None
    lang = resolve_language(request)
    context = build_admin_context(
        request,
        actor,
        title=pick_lang(lang, "Agent 管理", "Agents"),
        content=pick_lang(lang, "邀请、审批和管理 Agent。", "Invite, approve, and manage Agents."),
        page_kicker=pick_lang(lang, "Agent", "Agent"),
        page_eyebrow=pick_lang(lang, "控制台", "Console"),
    )
    rows = agent_service.list_enrollments(db)
    context.update(enrollments=rows, invitation=None)
    return templates_for(request).TemplateResponse(request, "agents.html", context)


@router.post("/agents/invitations", response_class=HTMLResponse)
async def create_agent_invitation(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    blocked, actor = _maintainer(request, db)
    if blocked is not None:
        return blocked
    assert actor is not None and actor.principal is not None
    values = await _form(request)
    payload = AgentInvitationCreateRequest(
        slug=values.get("slug", ""),
        display_name=values.get("display_name", ""),
        expires_in_minutes=int(values.get("expires_in_minutes", "30")),
        max_daily_publishes=int(values.get("max_daily_publishes", "100")),
        auto_public_publish=values.get("auto_public_publish") == "true",
    )
    try:
        invitation, raw, prompt = agent_service.create_invitation(
            db,
            slug=payload.slug,
            display_name=payload.display_name,
            expires_in_minutes=payload.expires_in_minutes,
            max_daily_publishes=payload.max_daily_publishes,
            auto_public_publish=payload.auto_public_publish,
            creator_principal_id=actor.principal.id,
            base_url=str(request.base_url).rstrip("/"),
        )
    except agent_service.AgentEnrollmentConflict as exc:
        return HTMLResponse(str(exc), status_code=409)
    context = build_admin_context(
        request,
        actor,
        title="Agent invitation created",
        content="Copy this one-time prompt to the Agent.",
        page_kicker="Agent",
        page_eyebrow="Invitation",
    )
    context.update(
        invitation={
            "public_id": invitation.public_id,
            "slug": payload.slug,
            "prompt": f"{prompt}\n\nInvitation token (paste into stdin only):\n{raw}",
            "expires_at": invitation.expires_at.isoformat(),
        }
    )
    response = templates_for(request).TemplateResponse(
        request, "agent-invitation-created.html", context
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.post("/agents/enrollments/{enrollment_id}/approve", response_class=HTMLResponse)
async def approve_agent(
    enrollment_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    blocked, actor = _maintainer(request, db)
    if blocked is not None:
        return blocked
    assert actor is not None and actor.principal is not None
    try:
        values = await _form(request)
        agent_service.decide_enrollment(
            db,
            enrollment_id=enrollment_id,
            approve=True,
            actor_principal_id=actor.principal.id,
            fingerprint=values.get("fingerprint"),
            note=values.get("note", ""),
        )
    except agent_service.AgentEnrollmentError as exc:
        return HTMLResponse(str(exc), status_code=409)
    return Response(status_code=303, headers={"Location": "/agents"})


@router.post("/agents/enrollments/{enrollment_id}/reject", response_class=HTMLResponse)
async def reject_agent(
    enrollment_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    blocked, actor = _maintainer(request, db)
    if blocked is not None:
        return blocked
    assert actor is not None and actor.principal is not None
    try:
        values = await _form(request)
        agent_service.decide_enrollment(
            db,
            enrollment_id=enrollment_id,
            approve=False,
            actor_principal_id=actor.principal.id,
            fingerprint=None,
            note=values.get("note", ""),
        )
    except agent_service.AgentEnrollmentError as exc:
        return HTMLResponse(str(exc), status_code=409)
    return Response(status_code=303, headers={"Location": "/agents"})
