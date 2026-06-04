from __future__ import annotations

from fastapi import APIRouter, Depends

from server.auth import get_current_user
from server.models import User
from server.settings import get_settings

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/healthz")
def healthz():
    settings = get_settings()
    return {"ok": True, "service": settings.app_name}


@router.get("/api/v1/me")
def read_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }
