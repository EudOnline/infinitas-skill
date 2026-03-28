"""Auth API for token-based authentication."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.db import get_db
from server.models import User
from server.auth import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class TokenLoginRequest(BaseModel):
    token: str


class TokenLoginResponse(BaseModel):
    success: bool
    username: str | None = None
    error: str | None = None


@router.post("/login", response_model=TokenLoginResponse)
async def login(request: TokenLoginRequest, db: Session = Depends(get_db)):
    """Validate token and return user info."""
    user = db.query(User).filter(User.token == request.token).one_or_none()
    if user is None:
        return TokenLoginResponse(success=False, error="无效的 Token")
    return TokenLoginResponse(success=True, username=user.username)


@router.get("/me")
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {"username": user.username, "role": user.role}
