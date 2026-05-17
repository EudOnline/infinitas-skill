from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server.api.activity import router as activity_router
from server.api.auth import router as auth_router
from server.api.background import router as background_router
from server.api.library import router as library_router
from server.api.object_tokens import router as object_tokens_router
from server.api.profile import credentials_router as credentials_router, router as profile_router
from server.api.publish import router as publish_router
from server.api.search import router as search_router
from server.auth import get_current_user
from server.db import ensure_database_ready, get_db
from server.exceptions import register_exception_handlers
from server.middleware import CsrfValidationMiddleware, SecurityHeadersMiddleware
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
from server.modules.shares.router import router as shares_router
from server.settings import get_settings
from server.ui.routes import register_ui_routes


def create_app() -> FastAPI:
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    ensure_database_ready()

    app = FastAPI(title="infinitas hosted registry", docs_url="/api/docs", redoc_url="/api/redoc")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.environment == "production":
        app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(CsrfValidationMiddleware)
    app.mount("/static", StaticFiles(directory=str(settings.template_dir.parent / "static")), name="static")

    @app.get("/healthz")
    def healthz(db: Session = Depends(get_db)):
        user_count = db.scalar(select(func.count()).select_from(User)) or 0
        return {"ok": True, "service": settings.app_name, "users": user_count}

    @app.get("/api/v1/me")
    def read_me(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role}

    register_exception_handlers(app, templates)
    register_ui_routes(app, templates, settings)
    for router in (
        activity_router, profile_router, credentials_router, library_router,
        object_tokens_router, publish_router, auth_router, background_router,
        search_router, access_router, agent_code_router, agent_preset_router,
        authoring_router, discovery_router, release_router, exposure_router,
        review_router, shares_router, registry_router,
    ):
        app.include_router(router)
    return app

app = create_app()
