from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from server.ui.formatting import build_kawaii_ui_context
from server.ui.i18n import pick_lang, resolve_language


def register_exception_handlers(app, templates: Jinja2Templates) -> None:
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
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
                "message": pick_lang(lang, "您访问的页面不存在。", "The page you are looking for does not exist."),
                **build_kawaii_ui_context(request, lang, "", ""),
            },
            status_code=404,
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
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
                "message": pick_lang(lang, "出了点问题，请稍后再试。", "Something went wrong. Please try again later."),
                **build_kawaii_ui_context(request, lang, "", ""),
            },
            status_code=500,
        )
