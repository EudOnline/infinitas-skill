"""Background API for managing user backgrounds."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.auth_guards import require_user_with_context
from server.db import get_db
from server.modules.access.authn import AccessContext

router = APIRouter(prefix="/api/v1/background", tags=["background"])

# Preset backgrounds using CSS gradients only (no external URLs)
BACKGROUND_PRESETS = {
    "light": [
        {"id": "sakura-street", "name": "樱花街道", "url": None},
        {"id": "anime-sky", "name": "动漫天空", "url": None},
        {"id": "city-sunset", "name": "城市日落", "url": None},
        {"id": "cherry-blossom", "name": "樱花盛开", "url": None},
        {"id": "gradient-pink", "name": "粉色渐变", "url": None},
    ],
    "dark": [
        {"id": "starry-night", "name": "星空夜景", "url": None},
        {"id": "neon-city", "name": "霓虹城市", "url": None},
        {"id": "aurora", "name": "极光", "url": None},
        {"id": "cyberpunk", "name": "赛博朋克", "url": None},
        {"id": "gradient-dark", "name": "深色渐变", "url": None},
    ],
}


class BackgroundListResponse(BaseModel):
    presets: dict


class UserBackgroundResponse(BaseModel):
    light_bg_id: str | None
    dark_bg_id: str | None


class SetBackgroundRequest(BaseModel):
    theme: Literal["light", "dark"]
    bg_id: str = Field(min_length=1, max_length=100)


@router.get("/presets", response_model=BackgroundListResponse)
def get_background_presets():
    """Get available background presets."""
    return {"presets": BACKGROUND_PRESETS}


@router.get("/me", response_model=UserBackgroundResponse)
def get_user_background(context: AccessContext = Depends(get_current_access_context)):
    """Get current user's background settings."""
    require_user_with_context(context)
    return {
        "light_bg_id": context.user.light_bg_id,
        "dark_bg_id": context.user.dark_bg_id,
    }


@router.post("/set")
def set_background(
    request: SetBackgroundRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
):
    """Set user background (requires authentication)."""
    require_user_with_context(context)

    presets = BACKGROUND_PRESETS.get(request.theme, [])
    valid_ids = {p["id"] for p in presets}
    if request.bg_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Invalid background ID")

    if request.theme == "light":
        context.user.light_bg_id = request.bg_id
    else:
        context.user.dark_bg_id = request.bg_id

    db.commit()
    return {"success": True, "message": "Background updated"}
