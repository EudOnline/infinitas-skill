from __future__ import annotations

from fastapi import APIRouter

from server.settings import get_settings

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/healthz")
def healthz():
    settings = get_settings()
    return {"ok": True, "service": settings.app_name}
