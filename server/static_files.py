from __future__ import annotations

from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope


class CachedStaticFiles(StaticFiles):
    """StaticFiles with Cache-Control headers for production caching.

    - Hashed assets (containing ?v=): Cache-Control: max-age=31536000, immutable
    - Other assets: Cache-Control: max-age=3600 (1 hour)
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            query_string = scope.get("query_string", b"").decode()
            if "v=" in query_string:
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response
