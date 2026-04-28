from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server.api.auth import router as auth_router
from server.api.background import router as background_router
from server.api.library import router as library_router
from server.api.search import router as search_router
from server.auth import get_current_user
from server.db import ensure_database_ready, get_db
from server.models import User
from server.modules.access.router import router as access_router
from server.modules.agent_codes.router import router as agent_code_router
from server.modules.agent_presets.router import router as agent_preset_router
from server.modules.authoring.router import router as authoring_router
from server.modules.discovery.router import router as discovery_router
from server.modules.exposure.router import router as exposure_router
from server.modules.registry.router import router as registry_router
from server.modules.release.router import router as release_router
from server.modules.review.router import router as review_router
from server.security import SecurityHeadersMiddleware
from server.settings import get_settings
from server.ui.routes import register_ui_routes


def create_app() -> FastAPI:
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    ensure_database_ready()

    app = FastAPI(title="infinitas hosted registry")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=str(settings.template_dir.parent / "static")), name="static")

    @app.get("/healthz")
    def healthz(db: Session = Depends(get_db)):
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        return {"ok": True, "service": settings.app_name, "users": user_count}

    @app.get("/api/v1/me")
    def read_me(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role}

    register_ui_routes(app, templates, settings)
    app.include_router(library_router)
    app.include_router(auth_router)
    app.include_router(background_router)
    app.include_router(search_router)
    app.include_router(access_router)
    app.include_router(agent_code_router)
    app.include_router(agent_preset_router)
    app.include_router(authoring_router)
    app.include_router(discovery_router)
    app.include_router(release_router)
    app.include_router(exposure_router)
    app.include_router(review_router)
    app.include_router(registry_router)
    return app

app = create_app()
