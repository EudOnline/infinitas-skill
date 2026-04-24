from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' "
    "'sha256-dkACincQ35HE+JH32YH7iAxfFFDeZtankjXNpNEgklY='; "
    "style-src 'self' https://fonts.googleapis.com "
    "'sha256-8iqIHeXI7vKpcWNJ+Hs0m+zIMcRd14lh0MpgkhEjZ9Y='; "
    "img-src 'self' data: https:; "
    "font-src 'self' https://fonts.gstatic.com; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


__all__ = ["SecurityHeadersMiddleware"]
