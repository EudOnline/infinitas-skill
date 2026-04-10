from __future__ import annotations

from fastapi import Depends, FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from server.api.auth import router as auth_router
from server.api.background import router as background_router
from server.api.search import router as search_router
from server.auth import get_current_user
from server.db import ensure_database_ready, get_db
from server.models import User
from server.modules.access.router import router as access_router
from server.modules.authoring.router import router as authoring_router
from server.modules.discovery.router import router as discovery_router
from server.modules.exposure.router import router as exposure_router
from server.modules.registry.router import router as registry_router
from server.modules.release.router import router as release_router
from server.modules.review.router import router as review_router
from server.settings import get_settings
from server.ui.routes import register_ui_routes


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Content Security Policy: strict defaults; sha256 hash allows the single
        # FOUC-prevention inline script in layout-kawaii.html. All styles are external.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'sha256-ar/VU9VE8tNRN7ArC3tn79WXi8NBFxtlCWZbdPWC9DY=' 'sha256-wNKOOyXugCvfTTx1FxAaRCPD1avcNpcT4A5B2DyVcRk='; "
            "style-src 'self' https://fonts.googleapis.com 'sha256-moDlO93Iogi/ZoWcbewBvTchxXFk3sinw74H2TaTwV0=' 'sha256-1rshEoZLuXCj3aaL1spgfDYvH7U4fq9LORaYcVwNAxs='; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_app() -> FastAPI:
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    ensure_database_ready()

    app = FastAPI(title="infinitas hosted registry")
    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=str(settings.template_dir.parent / "static")), name="static")

    @app.get("/healthz")
    def healthz(db: Session = Depends(get_db)):
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        return {"ok": True, "service": settings.app_name, "users": user_count}

    @app.get("/api/v1/me")
    def read_me(user: User = Depends(get_current_user)):
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        }

    register_ui_routes(app, templates, settings)

    app.include_router(auth_router)
    app.include_router(background_router)
    app.include_router(search_router)
    app.include_router(access_router)
    app.include_router(authoring_router)
    app.include_router(discovery_router)
    app.include_router(release_router)
    app.include_router(exposure_router)
    app.include_router(review_router)
    app.include_router(registry_router)
    return app


app = create_app()
