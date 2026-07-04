from __future__ import annotations

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemBytecodeCache
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server.api.activity import router as activity_router
from server.api.auth import router as auth_router
from server.api.library import router as library_router
from server.api.object_tokens import router as object_tokens_router
from server.api.profile import credentials_router
from server.api.profile import router as profile_router
from server.api.search import router as search_router
from server.api.share_links import router as share_links_router
from server.api.system import router as system_router
from server.db import ensure_database_ready
from server.exceptions import register_exception_handlers
from server.logging import configure_logging
from server.middleware import CsrfValidationMiddleware, SecurityHeadersMiddleware
from server.modules.access.router import router as access_router
from server.modules.authoring.router import router as authoring_router
from server.modules.discovery.router import router as discovery_router
from server.modules.exposure.router import router as exposure_router
from server.modules.registry.router import router as registry_router
from server.modules.release.router import router as release_router
from server.modules.review.router import router as review_router
from server.settings import get_settings
from server.static_files import CachedStaticFiles
from server.ui.assets import load_asset_hashes, static_url_factory
from server.ui.routes import register_ui_routes


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    asset_hashes = load_asset_hashes(settings.template_dir.parent / "static")
    templates.env.globals["asset_hashes"] = asset_hashes
    templates.env.globals["static_url"] = static_url_factory(asset_hashes)
    ensure_database_ready()
    docs_url = "/api/docs" if settings.environment != "production" else None
    redoc_url = "/api/redoc" if settings.environment != "production" else None
    app = FastAPI(title="infinitas hosted registry", docs_url=docs_url, redoc_url=redoc_url)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.environment == "production":
        cache_dir = settings.root_dir / ".cache" / "jinja2"
        cache_dir.mkdir(parents=True, exist_ok=True)
        templates.env.bytecode_cache = FileSystemBytecodeCache(str(cache_dir))
        app.add_middleware(HTTPSRedirectMiddleware)
    app.add_middleware(CsrfValidationMiddleware)
    static_root = str(settings.template_dir.parent / "static")
    app.mount("/static", CachedStaticFiles(directory=static_root), name="static")
    register_exception_handlers(app, templates)
    register_ui_routes(app, templates, settings)
    for router in (
        system_router,
        activity_router,
        profile_router,
        credentials_router,
        library_router,
        object_tokens_router,
        auth_router,
        search_router,
        access_router,
        authoring_router,
        discovery_router,
        release_router,
        exposure_router,
        review_router,
        share_links_router,
        registry_router,
    ):
        app.include_router(router)
    return app


app = create_app()
