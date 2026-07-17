from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemBytecodeCache
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server.exceptions import register_exception_handlers
from server.lifecycle import lifespan
from server.logging import configure_logging
from server.middleware import CsrfValidationMiddleware, SecurityHeadersMiddleware
from server.modules.access.router import routers as access_routers
from server.modules.audit.router import router as audit_router
from server.modules.authoring.router import router as authoring_router
from server.modules.discovery.router import routers as discovery_routers
from server.modules.exposure.router import router as exposure_router
from server.modules.identity.router import routers as identity_routers
from server.modules.library.router import router as library_router
from server.modules.registry.router import router as registry_router
from server.modules.release.router import router as release_router
from server.modules.review.router import router as review_router
from server.modules.system.router import router as system_router
from server.settings import Settings, get_settings
from server.static_files import CachedStaticFiles
from server.ui.assets import load_asset_hashes, static_url_factory
from server.ui.routes.home import router as home_ui_router
from server.ui.routes.library import router as library_ui_router
from server.ui.routes.profile import router as profile_ui_router
from server.ui.routes.settings import router as settings_ui_router


def _dependency_requires_auth(dependency: Any) -> bool:
    call = getattr(dependency, "call", None)
    module = getattr(call, "__module__", "")
    name = getattr(call, "__name__", "")
    if module == "server.modules.identity.auth" and name in {
        "get_current_access_context",
        "get_current_user",
    }:
        return True
    return any(_dependency_requires_auth(item) for item in dependency.dependencies)


def _iter_api_routes(routes: list[Any]) -> list[APIRoute]:
    result: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            result.append(route)
            continue
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            result.extend(_iter_api_routes(list(original_router.routes)))
    return result


def _install_openapi(application: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            openapi_version=application.openapi_version,
            description=application.description,
            routes=application.routes,
        )
        components = schema.setdefault("components", {})
        components.setdefault("securitySchemes", {}).update(
            {
                "BearerAuth": {"type": "http", "scheme": "bearer"},
                "SessionCookie": {
                    "type": "apiKey",
                    "in": "cookie",
                    "name": "infinitas_auth_token",
                },
            }
        )
        for route in _iter_api_routes(list(application.routes)):
            if not _dependency_requires_auth(route.dependant):
                continue
            path_item = schema.get("paths", {}).get(route.path)
            if not path_item:
                continue
            for method in route.methods or set():
                operation = path_item.get(method.lower())
                if operation is not None:
                    operation["security"] = [{"BearerAuth": []}, {"SessionCookie": []}]
        application.openapi_schema = schema
        return schema

    application.openapi = custom_openapi  # type: ignore[method-assign]


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or get_settings()
    templates = Jinja2Templates(directory=str(settings.template_dir))
    asset_hashes = load_asset_hashes(settings.template_dir.parent / "static")
    templates.env.globals["asset_hashes"] = asset_hashes
    templates.env.globals["static_url"] = static_url_factory(asset_hashes)
    docs_url = "/api/docs" if settings.environment != "production" else None
    redoc_url = "/api/redoc" if settings.environment != "production" else None
    application = FastAPI(
        title="infinitas hosted registry",
        docs_url=docs_url,
        redoc_url=redoc_url,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.templates = templates
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    application.add_middleware(SecurityHeadersMiddleware)
    if settings.environment == "production":
        cache_dir = settings.root_dir / ".cache" / "jinja2"
        cache_dir.mkdir(parents=True, exist_ok=True)
        templates.env.bytecode_cache = FileSystemBytecodeCache(str(cache_dir))
        application.add_middleware(HTTPSRedirectMiddleware)
    application.add_middleware(CsrfValidationMiddleware)
    static_root = str(settings.template_dir.parent / "static")
    application.mount("/static", CachedStaticFiles(directory=static_root), name="static")
    register_exception_handlers(application, templates)
    for router in (
        system_router,
        audit_router,
        library_router,
        authoring_router,
        release_router,
        exposure_router,
        review_router,
        registry_router,
        *identity_routers,
        *access_routers,
        *discovery_routers,
        home_ui_router,
        library_ui_router,
        profile_ui_router,
        settings_ui_router,
    ):
        application.include_router(router)
    _install_openapi(application)
    return application


app = create_app()
