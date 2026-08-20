from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

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

log = get_logger(__name__)
UiContextBuilder = Callable[[Request, str, str, str], dict[str, Any]]


def _request_wants_json(request: Request) -> bool:
    """Keep machine-facing API errors JSON when clients omit Accept."""
    path = request.url.path
    return (
        path == "/api"
        or path.startswith("/api/")
        or request.headers.get("accept", "").startswith("application/json")
    )


def _error_page(
    request: Request,
    *,
    templates: Jinja2Templates,
    build_ui_context: UiContextBuilder,
    status_code: int,
    title: tuple[str, str],
    message: tuple[str, str],
) -> Response:
    lang = resolve_language(request)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "request": request,
            "status_code": status_code,
            "title": pick_lang(lang, *title),
            "message": pick_lang(lang, *message),
            **build_ui_context(request, lang, "", ""),
        },
        status_code=status_code,
    )


def register_exception_handlers(
    app: FastAPI,
    templates: Jinja2Templates,
    build_ui_context: UiContextBuilder,
) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_exc_handler(request: Request, exc: NotFoundError) -> Response:
        if _request_wants_json(request):
            return JSONResponse({"detail": str(exc) or "Not found"}, status_code=404)
        return _error_page(
            request,
            templates=templates,
            build_ui_context=build_ui_context,
            status_code=404,
            title=("未找到", "Not Found"),
            message=("您访问的页面不存在。", "The page you are looking for does not exist."),
        )

    @app.exception_handler(ForbiddenError)
    async def forbidden_exc_handler(request: Request, exc: ForbiddenError) -> Response:
        if _request_wants_json(request):
            return JSONResponse({"detail": str(exc) or "Forbidden"}, status_code=403)
        return _error_page(
            request,
            templates=templates,
            build_ui_context=build_ui_context,
            status_code=403,
            title=("禁止访问", "Forbidden"),
            message=(
                "您没有权限访问此资源。",
                "You do not have permission to access this resource.",
            ),
        )

    @app.exception_handler(ConflictError)
    async def conflict_exc_handler(request: Request, exc: ConflictError) -> Response:
        return JSONResponse({"detail": str(exc) or "Conflict"}, status_code=409)

    @app.exception_handler(ValidationError)
    async def validation_exc_handler(request: Request, exc: ValidationError) -> Response:
        return JSONResponse({"detail": str(exc) or "Validation error"}, status_code=422)

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> Response:
        if _request_wants_json(request):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return _error_page(
            request,
            templates=templates,
            build_ui_context=build_ui_context,
            status_code=404,
            title=("未找到", "Not Found"),
            message=("您访问的页面不存在。", "The page you are looking for does not exist."),
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc: Exception) -> Response:
        log.error(
            "500 internal server error: %s %s\n%s",
            request.method,
            request.url.path,
            traceback.format_exc(),
        )
        if _request_wants_json(request):
            return JSONResponse({"detail": "Internal server error"}, status_code=500)
        return _error_page(
            request,
            templates=templates,
            build_ui_context=build_ui_context,
            status_code=500,
            title=("服务器错误", "Server Error"),
            message=("出了点问题，请稍后再试。", "Something went wrong. Please try again later."),
        )
