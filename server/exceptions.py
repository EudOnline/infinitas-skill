from __future__ import annotations

import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.templating import Jinja2Templates

from server.exceptions_base import (  # noqa: F401
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from server.i18n import pick_lang, resolve_language
from server.logging import get_logger
from server.ui.formatting import build_kawaii_ui_context

log = get_logger(__name__)


def register_exception_handlers(app: FastAPI, templates: Jinja2Templates) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_exc_handler(request: Request, exc: NotFoundError) -> Response:
        lang = resolve_language(request)
        if request.headers.get("accept", "").startswith("application/json"):
            return JSONResponse({"detail": str(exc) or "Not found"}, status_code=404)
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "status_code": 404,
                "title": pick_lang(lang, "未找到", "Not Found"),
                "message": pick_lang(
                    lang, "您访问的页面不存在。", "The page you are looking for does not exist."
                ),
                **build_kawaii_ui_context(request, lang, "", ""),
            },
            status_code=404,
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_exc_handler(request: Request, exc: ForbiddenError) -> Response:
        lang = resolve_language(request)
        if request.headers.get("accept", "").startswith("application/json"):
            return JSONResponse({"detail": str(exc) or "Forbidden"}, status_code=403)
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "status_code": 403,
                "title": pick_lang(lang, "禁止访问", "Forbidden"),
                "message": pick_lang(
                    lang,
                    "您没有权限访问此资源。",
                    "You do not have permission to access this resource.",
                ),
                **build_kawaii_ui_context(request, lang, "", ""),
            },
            status_code=403,
        )

    @app.exception_handler(ConflictError)
    async def conflict_exc_handler(request: Request, exc: ConflictError) -> Response:
        return JSONResponse({"detail": str(exc) or "Conflict"}, status_code=409)

    @app.exception_handler(ValidationError)
    async def validation_exc_handler(request: Request, exc: ValidationError) -> Response:
        return JSONResponse({"detail": str(exc) or "Validation error"}, status_code=422)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> Response:
        lang = resolve_language(request)
        if request.headers.get("accept", "").startswith("application/json"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "status_code": 404,
                "title": pick_lang(lang, "未找到", "Not Found"),
                "message": pick_lang(
                    lang, "您访问的页面不存在。", "The page you are looking for does not exist."
                ),
                **build_kawaii_ui_context(request, lang, "", ""),
            },
            status_code=404,
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc: Exception) -> Response:
        log.error(
            "500 internal server error: %s %s\n%s",
            request.method,
            request.url.path,
            traceback.format_exc(),
        )
        lang = resolve_language(request)
        if request.headers.get("accept", "").startswith("application/json"):
            return JSONResponse({"detail": "Internal server error"}, status_code=500)
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "request": request,
                "status_code": 500,
                "title": pick_lang(lang, "服务器错误", "Server Error"),
                "message": pick_lang(
                    lang,
                    "出了点问题，请稍后再试。",
                    "Something went wrong. Please try again later.",
                ),
                **build_kawaii_ui_context(request, lang, "", ""),
            },
            status_code=500,
        )
