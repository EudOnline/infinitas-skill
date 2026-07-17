"""System health API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from server.settings import get_settings

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class HealthView(BaseModel):
    ok: bool
    service: str


@router.get("/healthz", response_model=HealthView)
def healthz() -> HealthView:
    """Health check endpoint.

    Returns a simple OK response to indicate the service is running.
    Used by load balancers and container orchestrators for liveness checks.

    Returns:
        dict with "ok" (bool) and "service" (str) fields
    """
    settings = get_settings()
    return HealthView(ok=True, service=settings.app_name)
