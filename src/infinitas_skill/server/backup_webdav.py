"""WebDAV transport for encrypted offsite backups."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn
from urllib.parse import quote

import httpx


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def remote_path(path: str) -> str:
    normalized = PurePosixPath("/" + path.strip("/"))
    if ".." in normalized.parts:
        fail(f"remote path must not contain parent traversal: {path}")
    return normalized.as_posix()


class WebDAVClient:
    def __init__(
        self,
        *,
        base_url: str,
        auth_mode: str,
        username: str,
        secret: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if auth_mode not in {"basic", "bearer"}:
            fail("WebDAV auth mode must be basic or bearer")
        if not secret:
            fail("WebDAV secret environment variable is empty")
        headers: dict[str, str] = {}
        if auth_mode == "basic":
            encoded = base64.b64encode(f"{username}:{secret}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        else:
            headers["Authorization"] = f"Bearer {secret}"
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers=headers,
            timeout=120,
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _url(self, remote_path_value: str) -> str:
        return quote(remote_path(remote_path_value).lstrip("/"), safe="/")

    def ensure_directories(self, remote_file: str) -> None:
        parts = PurePosixPath(remote_path(remote_file)).parent.parts[1:]
        current = ""
        for part in parts:
            current += f"/{part}"
            response = self._client.request("MKCOL", self._url(current))
            if response.status_code not in {201, 405}:
                fail(f"WebDAV MKCOL failed for {current}: HTTP {response.status_code}")

    def exists(self, remote_path_value: str) -> bool:
        response = self._client.request("HEAD", self._url(remote_path_value))
        if response.status_code in {200, 204}:
            return True
        if response.status_code == 404:
            return False
        fail(f"WebDAV HEAD failed for {remote_path_value}: HTTP {response.status_code}")

    def get_json(self, remote_path_value: str) -> dict[str, Any] | None:
        response = self._client.get(self._url(remote_path_value), follow_redirects=True)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            fail(f"WebDAV GET failed for {remote_path_value}: HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            fail(f"WebDAV receipt is not valid JSON: {remote_path_value}")
        if not isinstance(payload, dict):
            fail(f"WebDAV receipt must contain an object: {remote_path_value}")
        return payload

    def upload_file(self, local_path: Path, remote_path_value: str) -> None:
        with local_path.open("rb") as handle:
            response = self._client.put(self._url(remote_path_value), content=handle)
        if response.status_code not in {200, 201, 204}:
            fail(f"WebDAV PUT failed for {remote_path_value}: HTTP {response.status_code}")

    def upload_json_once(self, payload: dict[str, Any], remote_path_value: str) -> None:
        response = self._client.put(
            self._url(remote_path_value),
            content=json.dumps(payload, separators=(",", ":")).encode(),
            headers={"Content-Type": "application/json", "If-None-Match": "*"},
        )
        if response.status_code not in {200, 201, 204}:
            fail(f"WebDAV receipt PUT failed for {remote_path_value}: HTTP {response.status_code}")

    def download_file(self, remote_path_value: str, local_path: Path) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with self._client.stream(
            "GET", self._url(remote_path_value), follow_redirects=True
        ) as response:
            if response.status_code != 200:
                fail(f"WebDAV download failed for {remote_path_value}: HTTP {response.status_code}")
            with local_path.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        local_path.chmod(0o600)


def client_from_environment(
    *, base_url: str, auth_mode: str, user_env: str, secret_env: str
) -> WebDAVClient:
    username = os.environ.get(user_env, "")
    secret = os.environ.get(secret_env, "")
    if auth_mode == "basic" and not username:
        fail(f"WebDAV username environment variable is empty: {user_env}")
    return WebDAVClient(
        base_url=base_url,
        auth_mode=auth_mode,
        username=username,
        secret=secret,
    )
