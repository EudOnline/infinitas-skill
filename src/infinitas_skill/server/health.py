"""Dedicated healthcheck helpers for hosted server commands."""

from __future__ import annotations

import json
from urllib import error, request

from infinitas_skill.server.repo_checks import check_artifacts, check_database, check_repo, fail


def normalize_health_url(api_url: str) -> str:
    base = api_url.rstrip('/')
    if base.endswith('/healthz'):
        return base
    return f'{base}/healthz'


def check_api(api_url: str) -> dict:
    health_url = normalize_health_url(api_url)
    req = request.Request(health_url, headers={'Accept': 'application/json'})
    try:
        with request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except error.HTTPError as exc:
        fail(f'health endpoint returned HTTP {exc.code}: {health_url}')
    except error.URLError as exc:
        fail(f'health endpoint request failed: {exc.reason}')
    except json.JSONDecodeError as exc:
        fail(f'health endpoint did not return JSON: {exc}')
    if payload.get('ok') is not True:
        fail(f'health endpoint did not report ok=true: {payload}')
    return {'url': health_url, 'ok': True, 'service': payload.get('service') or ''}


def emit_healthcheck_summary(summary: dict, *, as_json: bool):
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"OK: api {summary['api']['url']}")
    print(f"OK: repo {summary['repo']['path']} (clean={summary['repo']['clean']})")
    print(f"OK: artifacts {summary['artifacts']['path']}")
    print(f"OK: database {summary['database']['path']}")


def run_server_healthcheck(
    *,
    api_url: str,
    repo_path: str,
    artifact_path: str,
    database_url: str,
    token: str = '',
    as_json: bool = False,
) -> int:
    _ = token
    summary = {
        'ok': True,
        'api': check_api(api_url),
        'repo': check_repo(repo_path),
        'artifacts': check_artifacts(artifact_path),
        'database': check_database(database_url),
    }
    emit_healthcheck_summary(summary, as_json=as_json)
    return 0


__all__ = [
    'check_api',
    'emit_healthcheck_summary',
    'normalize_health_url',
    'run_server_healthcheck',
]
