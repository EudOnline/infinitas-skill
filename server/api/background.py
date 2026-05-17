"""Background API for managing user backgrounds."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.auth import get_current_user
from server.db import get_db
from server.models import User

router = APIRouter(prefix="/api/background", tags=["background"])


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
    ]
}


class BackgroundListResponse(BaseModel):
    presets: dict


class UserBackgroundResponse(BaseModel):
    light_bg_id: str | None
    dark_bg_id: str | None


class SetBackgroundRequest(BaseModel):
    theme: str  # "light" or "dark"
    bg_id: str  # 背景ID


@router.get("/presets", response_model=BackgroundListResponse)
async def get_background_presets():
    """Get available background presets."""
    return {"presets": BACKGROUND_PRESETS}


@router.get("/me", response_model=UserBackgroundResponse)
async def get_user_background(user: User = Depends(get_current_user)):
    """Get current user's background settings."""
    return {
        "light_bg_id": user.light_bg_id,
        "dark_bg_id": user.dark_bg_id
    }


@router.post("/set")
async def set_background(
    request: SetBackgroundRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set user background (requires authentication)."""
    # Validate theme
    if request.theme not in ["light", "dark"]:
        raise HTTPException(status_code=400, detail="Invalid theme")

    # Validate bg_id exists in presets
    presets = BACKGROUND_PRESETS.get(request.theme, [])
    valid_ids = [p["id"] for p in presets]
    if request.bg_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Invalid background ID")

    # Update user background
    if request.theme == "light":
        user.light_bg_id = request.bg_id
    else:
        user.dark_bg_id = request.bg_id

    db.commit()

    return {"success": True, "message": "Background updated"}
