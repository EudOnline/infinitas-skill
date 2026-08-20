from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

import server.modules.identity.agent_service as agent_service
from server.db import get_db
from server.modules.identity.agent_schemas import (
    AgentEnrollmentStatusView,
    AgentEnrollmentSubmitRequest,
    AgentEnrollmentSubmitView,
)

router = APIRouter(prefix="/api/v1", tags=["agent-enrollment"])


def _bearer(authorization: str | None, prefix: str) -> str:
    raw = str(authorization or "")
    if not raw.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = raw[7:].strip()
    if not token.startswith(prefix):
        raise HTTPException(status_code=401, detail="invalid enrollment credential")
    return token


@router.post(
    "/agent-enrollments",
    response_model=AgentEnrollmentSubmitView,
    status_code=status.HTTP_201_CREATED,
)
def submit_agent_enrollment(
    payload: AgentEnrollmentSubmitRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AgentEnrollmentSubmitView:
    invitation = _bearer(authorization, "enroll_")
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
    if invitation_row is None:
        raise HTTPException(status_code=409, detail="invitation not found")
    return AgentEnrollmentSubmitView(
        public_id=enrollment.public_id,
        state=enrollment.state,
        fingerprint=enrollment.fingerprint,
        expires_at=invitation_row.expires_at.isoformat(),
    )


@router.get("/agent-enrollments/{public_id}", response_model=AgentEnrollmentStatusView)
def poll_agent_enrollment(
    public_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> AgentEnrollmentStatusView:
    token = _bearer(authorization, "status_")
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
