from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.identity.auth import get_current_access_context
from server.modules.release.agent_publish_service import (
    AgentPublishConflict,
    AgentPublishForbidden,
    AgentPublishNotFound,
    create_or_get_publish_intent,
)
from server.modules.release.schemas import ReleaseView

router = APIRouter(prefix="/api/v1/agent", tags=["agent-publish"])


@router.post("/versions/{version_id}/publish", response_model=ReleaseView)
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
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return ReleaseView.from_model(release)


__all__ = ["router"]
