from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemBytecodeCache
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server.api.activity import router as activity_router
from server.api.auth import router as auth_router
from server.api.background import router as background_router
from server.api.library import router as library_router
from server.api.object_tokens import router as object_tokens_router
from server.api.profile import credentials_router as credentials_router
from server.api.profile import router as profile_router
from server.api.publish import router as publish_router
from server.api.search import router as search_router
from server.api.system import router as system_router
from server.db import ensure_database_ready
from server.exceptions import register_exception_handlers
from server.logging import configure_logging, get_logger
from server.middleware import CsrfValidationMiddleware, SecurityHeadersMiddleware
from server.settings import get_settings
from server.ui.assets import load_asset_hashes, static_url_factory
from server.ui.routes import register_ui_routes


def create_app() -> FastAPI:
    configure_logging()
    log = get_logger("server.app")
    settings = get_settings()
    log.info("starting infinitas hosted registry env=%s", settings.environment)
    templates = Jinja2Templates(directory=str(settings.template_dir))
    asset_hashes = load_asset_hashes(settings.template_dir.parent / "static")
    templates.env.globals["asset_hashes"] = asset_hashes
    templates.env.globals["static_url"] = static_url_factory(asset_hashes)
    if settings.environment == "production":
        cache_dir = settings.root_dir / ".cache" / "jinja2"
        cache_dir.mkdir(parents=True, exist_ok=True)
        templates.env.bytecode_cache = FileSystemBytecodeCache(str(cache_dir))
    ensure_database_ready()

    app = FastAPI(title="infinitas hosted registry", docs_url="/api/docs", redoc_url="/api/redoc")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.environment == "production":
        app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(CsrfValidationMiddleware)
    app.mount("/static", StaticFiles(directory=str(settings.template_dir.parent / "static")), name="static")

    register_exception_handlers(app, templates)
    register_ui_routes(app, templates, settings)
    for router in (
        system_router, activity_router, profile_router, credentials_router,
        library_router, object_tokens_router, publish_router, auth_router,
        background_router, search_router,
    ):
        app.include_router(router)
    from server.modules.access.router import router as access_router
    from server.modules.authoring.router import router as authoring_router
    from server.modules.discovery.router import router as discovery_router
    from server.modules.exposure.router import router as exposure_router
    from server.modules.registry.router import router as registry_router
    from server.modules.release.router import router as release_router
    from server.modules.review.router import router as review_router
    from server.modules.shares.router import router as shares_router
    for router in (access_router, authoring_router, discovery_router, release_router,
                   exposure_router, review_router, shares_router, registry_router):
        app.include_router(router)
    return app


app = create_app()
