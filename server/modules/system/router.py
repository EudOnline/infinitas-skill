"""System health API."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from server.db import session_scope
from server.settings import get_settings

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class HealthView(BaseModel):
    ok: bool
    service: str


class ReadinessView(HealthView):
    checks: dict[str, bool]


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


@router.get(
    "/readyz",
    response_model=ReadinessView,
    responses={
        503: {
            "model": ReadinessView,
            "description": "A required runtime dependency is unavailable",
        }
    },
)
def readyz() -> ReadinessView | JSONResponse:
    """Report whether the API can serve its single-node production contract."""
    settings = get_settings()
    checks = {
        "database": _database_is_ready(),
        "repo": (settings.repo_path / ".git").exists(),
        "artifacts": settings.artifact_path.is_dir(),
    }
    if not all(checks.values()):
        payload = ReadinessView(ok=False, service=settings.app_name, checks=checks)
        return JSONResponse(status_code=503, content=payload.model_dump())
    return ReadinessView(ok=True, service=settings.app_name, checks=checks)


def _database_is_ready() -> bool:
    try:
        with session_scope() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        return False
    return True
