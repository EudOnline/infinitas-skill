from __future__ import annotations

from typing import Any, cast
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

import server.modules.identity.agent_lifecycle as agent_lifecycle
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


def _agents_response(
    request: Request,
    db: Session,
    actor: AccessContext,
    *,
    status_code: int = 200,
    form_error: str | None = None,
    form_values: dict[str, str] | None = None,
) -> Response:
    lang = resolve_language(request)
    agents = agent_lifecycle.list_agents(db)
    context = build_admin_context(
        request,
        actor,
        title=pick_lang(lang, "Agent 管理", "Agents"),
        content=pick_lang(lang, "邀请、审批和管理 Agent。", "Invite, approve, and manage Agents."),
        page_kicker=pick_lang(lang, "Agent", "Agent"),
        page_eyebrow=pick_lang(lang, "控制台", "Console"),
    )
    context.update(
        enrollments=agent_service.list_enrollments(db),
        agents=agents,
        reservations=agent_lifecycle.list_reservations(db),
        invitations=agent_lifecycle.list_invitations(db),
        invitation=None,
        invitation_request_nonce=agent_service.new_invitation_request_nonce(),
        recovery_request_nonces={
            service.id: agent_service.new_invitation_request_nonce()
            for service, _principal in agents
        },
        form_error=form_error,
        form_values=form_values or {},
    )
    return templates_for(request).TemplateResponse(
        request,
        "agents.html",
        context,
        status_code=status_code,
    )


def _invitation_response(
    request: Request,
    actor: AccessContext,
    *,
    invitation: Any,
    slug: str,
    prompt: str,
    raw: str,
) -> Response:
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
            "slug": slug,
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


@router.get("/agents", response_class=HTMLResponse)
def agents_page(request: Request, db: Session = Depends(get_db)) -> Response:
    blocked, actor = _maintainer(request, db)
    if blocked is not None:
        return blocked
    assert actor is not None
    return _agents_response(request, db, actor)


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
    form_values = {
        **values,
        "auto_public_publish": ("true" if values.get("auto_public_publish") == "true" else "false"),
    }
    try:
        payload = AgentInvitationCreateRequest.model_validate(
            {
                **form_values,
                "auto_public_publish": values.get("auto_public_publish") == "true",
            }
        )
        invitation, raw, prompt = agent_service.create_invitation(
            db,
            slug=payload.slug,
            request_nonce=payload.request_nonce,
            display_name=payload.display_name,
            expires_in_minutes=payload.expires_in_minutes,
            max_daily_publishes=payload.max_daily_publishes,
            auto_public_publish=payload.auto_public_publish,
            creator_principal_id=actor.principal.id,
            base_url=str(request.base_url).rstrip("/"),
        )
    except ValidationError as exc:
        error = exc.errors(include_url=False)[0]
        return _agents_response(
            request,
            db,
            actor,
            status_code=422,
            form_error=str(error.get("msg") or "Invalid invitation settings"),
            form_values=form_values,
        )
    except agent_service.AgentEnrollmentConflict as exc:
        return _agents_response(
            request,
            db,
            actor,
            status_code=409,
            form_error=str(exc),
            form_values=form_values,
        )
    return _invitation_response(
        request, actor, invitation=invitation, slug=payload.slug, prompt=prompt, raw=raw
    )


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
            enrollment_public_id=values.get("enrollment_public_id"),
            fingerprint=values.get("fingerprint"),
            note=values.get("note", ""),
        )
    except agent_service.AgentEnrollmentError as exc:
        return HTMLResponse(str(exc), status_code=409)
    return Response(status_code=303, headers={"Location": "/agents"})


async def _lifecycle_action(
    request: Request,
    db: Session,
    action: Any,
) -> Response:
    blocked, actor = _maintainer(request, db)
    if blocked is not None:
        return blocked
    assert actor is not None and actor.principal is not None
    try:
        action(actor.principal.id)
    except agent_service.AgentEnrollmentError as exc:
        return HTMLResponse(str(exc), status_code=409)
    return Response(status_code=303, headers={"Location": "/agents"})


@router.post("/agents/invitations/{invitation_id}/revoke", response_class=HTMLResponse)
async def revoke_agent_invitation(
    invitation_id: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    return await _lifecycle_action(
        request,
        db,
        lambda actor_id: agent_lifecycle.revoke_invitation(
            db, invitation_id=invitation_id, actor_principal_id=actor_id
        ),
    )


@router.post("/agents/reservations/{reservation_id}/release", response_class=HTMLResponse)
async def release_agent_reservation(
    reservation_id: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    return await _lifecycle_action(
        request,
        db,
        lambda actor_id: agent_lifecycle.release_reservation(
            db, reservation_id=reservation_id, actor_principal_id=actor_id
        ),
    )


async def _transition_agent(
    service_id: int, action: str, request: Request, db: Session
) -> Response:
    return await _lifecycle_action(
        request,
        db,
        lambda actor_id: agent_lifecycle.transition_agent(
            db, service_id=service_id, action=action, actor_principal_id=actor_id
        ),
    )


@router.post("/agents/{service_id}/suspend", response_class=HTMLResponse)
async def suspend_agent(
    service_id: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    return await _transition_agent(service_id, "suspend", request, db)


@router.post("/agents/{service_id}/resume", response_class=HTMLResponse)
async def resume_agent(
    service_id: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    return await _transition_agent(service_id, "resume", request, db)


@router.post("/agents/{service_id}/revoke", response_class=HTMLResponse)
async def revoke_agent(
    service_id: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    return await _transition_agent(service_id, "revoke", request, db)


@router.post("/agents/{service_id}/recovery-invitations", response_class=HTMLResponse)
async def create_agent_recovery_invitation(
    service_id: int, request: Request, db: Session = Depends(get_db)
) -> Response:
    blocked, actor = _maintainer(request, db)
    if blocked is not None:
        return blocked
    assert actor is not None and actor.principal is not None
    values = await _form(request)
    try:
        expires = int(values.get("expires_in_minutes", "30"))
        if not 5 <= expires <= 1440:
            raise ValueError
        invitation, raw, prompt = agent_lifecycle.create_recovery_invitation(
            db,
            service_id=service_id,
            request_nonce=values.get("request_nonce", ""),
            expires_in_minutes=expires,
            actor_principal_id=actor.principal.id,
            base_url=str(request.base_url).rstrip("/"),
        )
    except ValueError:
        return HTMLResponse("invalid recovery invitation expiry", status_code=422)
    except agent_service.AgentEnrollmentError as exc:
        return HTMLResponse(str(exc), status_code=409)
    service = db.get(agent_service.ServicePrincipal, service_id)
    assert service is not None
    return _invitation_response(
        request, actor, invitation=invitation, slug=service.slug, prompt=prompt, raw=raw
    )


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
            enrollment_public_id=None,
            fingerprint=None,
            note=values.get("note", ""),
        )
    except agent_service.AgentEnrollmentError as exc:
        return HTMLResponse(str(exc), status_code=409)
    return Response(status_code=303, headers={"Location": "/agents"})
