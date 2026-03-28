"""Background API for managing user backgrounds."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.db import get_db
from server.models import User
from server.auth import get_current_user

router = APIRouter(prefix="/api/background", tags=["background"])


# 预置背景图库
BACKGROUND_PRESETS = {
    "light": [
        {"id": "sakura-street", "name": "樱花街道", "url": "https://images.unsplash.com/photo-1578632767115-351597cf2477?w=1920&q=80"},
        {"id": "anime-sky", "name": "动漫天空", "url": "https://images.unsplash.com/photo-1560972550-aba3456b5564?w=1920&q=80"},
        {"id": "city-sunset", "name": "城市日落", "url": "https://images.unsplash.com/photo-1514565131-fce0801e5785?w=1920&q=80"},
        {"id": "cherry-blossom", "name": "樱花盛开", "url": "https://images.unsplash.com/photo-1522383225653-ed111181a951?w=1920&q=80"},
        {"id": "gradient-pink", "name": "粉色渐变", "url": None},
    ],
    "dark": [
        {"id": "starry-night", "name": "星空夜景", "url": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=1920&q=80"},
        {"id": "neon-city", "name": "霓虹城市", "url": "https://images.unsplash.com/photo-1519681393784-d120267933ba?w=1920&q=80"},
        {"id": "aurora", "name": "极光", "url": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=1920&q=80"},
        {"id": "cyberpunk", "name": "赛博朋克", "url": "https://images.unsplash.com/photo-1555680202-c86f0e12f086?w=1920&q=80"},
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
