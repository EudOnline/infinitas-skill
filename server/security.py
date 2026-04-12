from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' "
    "'sha256-ar/VU9VE8tNRN7ArC3tn79WXi8NBFxtlCWZbdPWC9DY=' "
    "'sha256-wNKOOyXugCvfTTx1FxAaRCPD1avcNpcT4A5B2DyVcRk=' "
    "'sha256-3xJ/QNdAqWt7Ege5LVwfJRv9pldWA6B3WgB4W4wMb1U=' "
    "'sha256-SEM1XvNi01/Or3XH+WjjcOnukATMP1rvJraUKPEtUQ8='; "
    "style-src 'self' https://fonts.googleapis.com "
    "'sha256-moDlO93Iogi/ZoWcbewBvTchxXFk3sinw74H2TaTwV0=' "
    "'sha256-1rshEoZLuXCj3aaL1spgfDYvH7U4fq9LORaYcVwNAxs=' "
    "'sha256-2IS4J3Z5MV8bfRbOEiTvcXAPo2OWtZtXuW50xmgAHJs='; "
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
