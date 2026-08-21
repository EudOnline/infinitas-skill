from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import server.modules.identity.agent_lifecycle as agent_lifecycle
import server.modules.identity.agent_service as agent_service
from server.db import get_db, session_scope
from server.modules.access.authn import AccessContext
from server.modules.identity.agent_schemas import (
    AgentCredentialRotateRequest,
    AgentCredentialRotateView,
    AgentEnrollmentStatusView,
    AgentEnrollmentSubmitRequest,
    AgentEnrollmentSubmitView,
)
from server.modules.identity.auth import get_current_access_context
from server.rate_limit import DBRateLimiter, resolve_rate_limit_key

router = APIRouter(prefix="/api/v1", tags=["agent-enrollment"])
_ENROLLMENT_SUBMIT_MAX = 10
_ENROLLMENT_POLL_MAX = 120
_ENROLLMENT_RATE_WINDOW = 60


def _bearer(authorization: str | None, prefix: str) -> str:
    raw = str(authorization or "")
    if not raw.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = raw[7:].strip()
    if not token.startswith(prefix):
        raise HTTPException(status_code=401, detail="invalid enrollment credential")
    return token


def _enforce_enrollment_rate_limit(
    request: Request,
    *,
    operation: str,
    token: str,
    max_attempts: int,
) -> None:
    client_key = resolve_rate_limit_key(request)
    token_key = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    keys = (
        f"agent-enrollment:{operation}:{client_key}",
        f"agent-enrollment:{operation}:token:{token_key}",
    )
    with session_scope() as rate_limit_db:
        limiter = DBRateLimiter(rate_limit_db)
        allowed = all(
            limiter.consume(
                key,
                max_attempts=max_attempts,
                window_seconds=_ENROLLMENT_RATE_WINDOW,
            )
            for key in keys
        )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Agent enrollment rate limit exceeded",
            headers={"Retry-After": str(_ENROLLMENT_RATE_WINDOW)},
        )


@router.post(
    "/agent-enrollments",
    response_model=AgentEnrollmentSubmitView,
    status_code=status.HTTP_201_CREATED,
    responses={
        410: {"description": "Invitation expired"},
        429: {"description": "Enrollment submission rate limit exceeded"},
    },
)
def submit_agent_enrollment(
    payload: AgentEnrollmentSubmitRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AgentEnrollmentSubmitView | JSONResponse:
    invitation = _bearer(authorization, "enroll_")
    _enforce_enrollment_rate_limit(
        request,
        operation="submit",
        token=invitation,
        max_attempts=_ENROLLMENT_SUBMIT_MAX,
    )
    try:
        enrollment = agent_service.submit_enrollment(
            db,
            raw_invitation=invitation,
            status_verifier=payload.status_verifier,
            api_key_verifier=payload.api_key_verifier,
            fingerprint=payload.fingerprint,
            runtime=payload.runtime,
        )
        invitation_row = db.get(agent_service.AgentInvitation, enrollment.invitation_id)
    except agent_service.AgentEnrollmentNotFound as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except agent_service.AgentEnrollmentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except agent_service.AgentEnrollmentExpired as exc:
        return JSONResponse(status_code=410, content={"detail": str(exc)})
    if invitation_row is None:
        raise HTTPException(status_code=409, detail="invitation not found")
    return AgentEnrollmentSubmitView(
        public_id=enrollment.public_id,
        state=enrollment.state,
        fingerprint=enrollment.fingerprint,
        expires_at=invitation_row.expires_at.isoformat(),
    )


@router.get(
    "/agent-enrollments/{public_id}",
    response_model=AgentEnrollmentStatusView,
    responses={429: {"description": "Enrollment polling rate limit exceeded"}},
)
def poll_agent_enrollment(
    public_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AgentEnrollmentStatusView:
    token = _bearer(authorization, "status_")
    _enforce_enrollment_rate_limit(
        request,
        operation="poll",
        token=token,
        max_attempts=_ENROLLMENT_POLL_MAX,
    )
    try:
        enrollment, invitation, principal = agent_service.status_for_token(db, token)
    except agent_service.AgentEnrollmentNotFound as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if enrollment.public_id != public_id:
        raise HTTPException(status_code=404, detail="enrollment not found")
    reservation = db.get(agent_service.AgentNamespaceReservation, invitation.reservation_id)
    if reservation is None:
        raise HTTPException(status_code=409, detail="namespace reservation not found")
    return AgentEnrollmentStatusView(
        public_id=enrollment.public_id,
        state=enrollment.state,
        slug=reservation.slug,
        fingerprint=enrollment.fingerprint,
        principal_slug=principal.slug if principal else None,
        principal_id=principal.id if principal else None,
        reason=enrollment.decision_note or None,
    )


@router.post(
    "/agent/credentials/rotate",
    response_model=AgentCredentialRotateView,
    responses={409: {"description": "Credential rotation conflict"}},
)
def rotate_agent_credential(
    payload: AgentCredentialRotateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> AgentCredentialRotateView:
    if context.principal is None:
        raise HTTPException(status_code=403, detail="Agent principal required")
    try:
        credential = agent_lifecycle.rotate_agent_credential(
            db,
            current_credential=context.credential,
            principal=context.principal,
            api_key_verifier=payload.api_key_verifier,
            fingerprint=payload.fingerprint,
            request_id=context.request_id,
        )
    except agent_service.AgentEnrollmentConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentCredentialRotateView(
        ok=True,
        credential_id=credential.id,
        fingerprint=payload.fingerprint,
    )
