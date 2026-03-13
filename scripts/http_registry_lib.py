#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin


DEFAULT_CATALOG_PATHS = {
    'ai_index': 'ai-index.json',
    'distributions': 'distributions.json',
    'compatibility': 'compatibility.json',
}


class HostedRegistryError(Exception):
    pass


def registry_catalog_path(reg: dict, key: str) -> str:
    overrides = reg.get('catalog_paths') if isinstance(reg.get('catalog_paths'), dict) else {}
    value = overrides.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return DEFAULT_CATALOG_PATHS[key]


def build_registry_url(base_url: str, path: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise HostedRegistryError('missing hosted registry base_url')
    if not isinstance(path, str) or not path.strip():
        raise HostedRegistryError('missing hosted registry path')
    return urljoin(base_url.rstrip('/') + '/', path.lstrip('/'))


def _request_headers(token_env: str | None = None) -> dict:
    headers = {}
    if token_env:
        token = os.environ.get(token_env)
        if not token:
            raise HostedRegistryError(f'missing bearer token in env {token_env}')
        headers['Authorization'] = f'Bearer {token}'
    return headers


def fetch_bytes(base_url: str, path: str, *, token_env: str | None = None) -> bytes:
    url = build_registry_url(base_url, path)
    request = urllib.request.Request(url, headers=_request_headers(token_env))
    try:
        with urllib.request.urlopen(request) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise HostedRegistryError(f'http {exc.code} while fetching {url}') from exc
    except urllib.error.URLError as exc:
        raise HostedRegistryError(f'could not reach hosted registry {url}: {exc.reason}') from exc


def fetch_json(base_url: str, path: str, *, token_env: str | None = None) -> dict:
    try:
        return json.loads(fetch_bytes(base_url, path, token_env=token_env).decode('utf-8'))
    except json.JSONDecodeError as exc:
        url = build_registry_url(base_url, path)
        raise HostedRegistryError(f'invalid json from hosted registry {url}: {exc}') from exc


def fetch_binary(base_url: str, path: str, output: Path, *, token_env: str | None = None) -> Path:
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    data = fetch_bytes(base_url, path, token_env=token_env)
    tmp_path = output.with_suffix(output.suffix + '.tmp')
    tmp_path.write_bytes(data)
    tmp_path.replace(output)
    return output
