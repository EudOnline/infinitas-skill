"""Hosted registry HTTP helpers."""

from __future__ import annotations

import json
import os
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from http.client import HTTPMessage
from pathlib import Path
from typing import IO, Any, cast
from urllib.parse import urljoin

DEFAULT_CATALOG_PATHS = {
    "ai_index": "ai-index.json",
    "distributions": "distributions.json",
    "compatibility": "compatibility.json",
}


class HostedRegistryError(Exception):
    pass


def registry_catalog_path(reg: dict, key: str) -> str:
    catalog_paths = reg.get("catalog_paths")
    overrides = catalog_paths if isinstance(catalog_paths, dict) else {}
    value = overrides.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return DEFAULT_CATALOG_PATHS[key]


def build_registry_url(base_url: str, path: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise HostedRegistryError("missing hosted registry base_url")
    if not isinstance(path, str) or not path.strip():
        raise HostedRegistryError("missing hosted registry path")
    base = urllib.parse.urlparse(base_url)
    if base.scheme not in ("https", "http") or not base.netloc:
        raise HostedRegistryError("hosted registry base_url must include an http(s) origin")
    path_value = path.strip()
    segments = urllib.parse.urlsplit(path_value).path.split("/")
    if any(segment == ".." for segment in segments):
        raise HostedRegistryError("hosted registry path may not contain '..'")
    if urllib.parse.urlsplit(path_value).scheme or urllib.parse.urlsplit(path_value).netloc:
        raise HostedRegistryError("hosted registry path must be relative")
    return urljoin(base_url.rstrip("/") + "/", path_value.lstrip("/"))


def _request_headers(token_env: str | None = None) -> dict:
    headers = {}
    if token_env:
        token = os.environ.get(token_env)
        if not token:
            raise HostedRegistryError(f"missing bearer token in env {token_env}")
        headers["Authorization"] = f"Bearer {token}"
    return headers


class _RedirectLimiter(urllib.request.HTTPRedirectHandler):
    def __init__(self, origin: tuple[str, str, int | None]) -> None:
        super().__init__()
        self._origin = origin
        self._count = 0

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        self._count += 1
        if self._count > 3:
            raise HostedRegistryError(f"too many redirects while fetching {req.full_url}")
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme not in ("https", "http"):
            raise HostedRegistryError(f"redirect to unsupported scheme {parsed.scheme!r}")
        redirect_origin = (
            parsed.scheme.lower(),
            (parsed.hostname or "").lower(),
            parsed.port,
        )
        if redirect_origin != self._origin:
            raise HostedRegistryError(
                f"redirect changed registry origin from {self._origin[1]} to {parsed.hostname}"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_bytes(base_url: str, path: str, *, token_env: str | None = None) -> bytes:
    url = build_registry_url(base_url, path)
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise HostedRegistryError(f"unsupported scheme {parsed.scheme!r} in registry URL")
    request = urllib.request.Request(url, headers=_request_headers(token_env))
    ctx = ssl.create_default_context()
    https_handler = urllib.request.HTTPSHandler(context=ctx)
    origin = (parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port)
    opener = urllib.request.build_opener(_RedirectLimiter(origin), https_handler)
    try:
        with opener.open(request) as response:
            data: bytes = response.read()
            return data
    except urllib.error.HTTPError as exc:
        raise HostedRegistryError(f"http {exc.code} while fetching {url}") from exc
    except urllib.error.URLError as exc:
        raise HostedRegistryError(f"could not reach hosted registry {url}: {exc.reason}") from exc


def fetch_json(base_url: str, path: str, *, token_env: str | None = None) -> dict[Any, Any]:
    try:
        result = json.loads(fetch_bytes(base_url, path, token_env=token_env).decode("utf-8"))
    except json.JSONDecodeError as exc:
        url = build_registry_url(base_url, path)
        raise HostedRegistryError(f"invalid json from hosted registry {url}: {exc}") from exc
    return cast(dict[Any, Any], result)


def fetch_binary(base_url: str, path: str, output: Path, *, token_env: str | None = None) -> Path:
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_bytes(base_url, path, token_env=token_env)
    fd, tmp_path = tempfile.mkstemp(dir=output.parent, prefix=output.name, suffix=".tmp")
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.replace(tmp_path, output)
    return output


__all__ = [
    "DEFAULT_CATALOG_PATHS",
    "HostedRegistryError",
    "registry_catalog_path",
    "build_registry_url",
    "fetch_bytes",
    "fetch_json",
    "fetch_binary",
]
