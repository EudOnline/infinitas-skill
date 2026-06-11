from __future__ import annotations

from fastapi import APIRouter

from server.settings import get_settings

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/healthz")
def healthz():
    """Health check endpoint.

    Returns a simple OK response to indicate the service is running.
    Used by load balancers and container orchestrators for liveness checks.

    Returns:
        dict with "ok" (bool) and "service" (str) fields
    """
    settings = get_settings()
    return {"ok": True, "service": settings.app_name}
