from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.credential_policy import CredentialPublishQuotaExceeded
from server.modules.identity.auth import get_current_access_context
from server.modules.release.agent_publish_service import (
    AgentPublishConflict,
    AgentPublishForbidden,
    AgentPublishNotFound,
    create_or_get_publish_intent,
    get_publish_status,
)
from server.modules.release.schemas import AgentPublishStatusView, ReleaseView
from server.modules.shared.formatting import iso_format

router = APIRouter(prefix="/api/v1/agent", tags=["agent-publish"])


@router.post(
    "/versions/{version_id}/publish",
    response_model=ReleaseView,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        200: {"description": "Existing Agent publish intent", "model": ReleaseView},
        429: {"description": "Agent daily publish quota exceeded"},
    },
)
def publish_agent_version(
    version_id: int,
    response: Response,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> ReleaseView:
    try:
        _intent, release, created = create_or_get_publish_intent(
            db, version_id=version_id, context=context
        )
    except AgentPublishNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentPublishForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AgentPublishConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CredentialPublishQuotaExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    response.status_code = status.HTTP_202_ACCEPTED if created else status.HTTP_200_OK
    return ReleaseView.from_model(release)


@router.get(
    "/publish-intents/{release_id}",
    response_model=AgentPublishStatusView,
)
def read_agent_publish_status(
    release_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> AgentPublishStatusView:
    try:
        intent, release = get_publish_status(db, release_id=release_id, context=context)
    except AgentPublishNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentPublishForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return AgentPublishStatusView(
        intent_id=intent.id,
        release_id=release.id,
        release_state=release.state,
        state=intent.state,
        reason=intent.reason or None,
        activated_at=iso_format(intent.activated_at),
    )


__all__ = ["router"]
