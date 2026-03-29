from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SERVER_ENV = 'development'
DEFAULT_SECRET_KEY = 'change-me'

DEFAULT_BOOTSTRAP_USERS = [
    {
        'username': 'maintainer',
        'display_name': 'Default Maintainer',
        'role': 'maintainer',
        'token': 'dev-maintainer-token',
    },
    {
        'username': 'contributor',
        'display_name': 'Default Contributor',
        'role': 'contributor',
        'token': 'dev-contributor-token',
    },
]


@dataclass(frozen=True)
class Settings:
    app_name: str
    root_dir: Path
    environment: str
    database_url: str
    secret_key: str
    template_dir: Path
    bootstrap_users: list[dict]
    repo_path: Path
    artifact_path: Path
    repo_lock_path: Path
    mirror_remote: str
    mirror_branch: str


def _normalize_bootstrap_users(payload: object) -> list[dict]:
    if not isinstance(payload, list):
        return []

    normalized = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        username = str(item.get('username') or '').strip()
        display_name = str(item.get('display_name') or username).strip()
        role = str(item.get('role') or 'contributor').strip() or 'contributor'
        token = str(item.get('token') or '').strip()
        if not username or not token:
            continue
        normalized.append(
            {
                'username': username,
                'display_name': display_name or username,
                'role': role,
                'token': token,
            }
        )
    return normalized


def _normalize_environment(raw: str | None) -> str:
    environment = str(raw or DEFAULT_SERVER_ENV).strip().lower() or DEFAULT_SERVER_ENV
    if environment not in {'development', 'test', 'production'}:
        raise RuntimeError(
            'INFINITAS_SERVER_ENV must be one of development, test, or production'
        )
    return environment


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name) or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _load_bootstrap_payload(raw: str | None, *, allow_default_fixture: bool) -> object:
    if not raw:
        return list(DEFAULT_BOOTSTRAP_USERS) if allow_default_fixture else None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return list(DEFAULT_BOOTSTRAP_USERS) if allow_default_fixture else None


def _normalize_string_list(payload: object) -> list[str]:
    if not isinstance(payload, list):
        return []
    normalized = []
    for item in payload:
        value = str(item or '').strip()
        if value:
            normalized.append(value)
    return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    environment = _normalize_environment(os.environ.get('INFINITAS_SERVER_ENV'))
    allow_insecure_defaults = environment in {'development', 'test'} or _env_flag(
        'INFINITAS_SERVER_ALLOW_INSECURE_DEFAULTS'
    )

    secret_key = str(os.environ.get('INFINITAS_SERVER_SECRET_KEY') or '').strip()
    if not secret_key and allow_insecure_defaults:
        secret_key = DEFAULT_SECRET_KEY
    if not secret_key or secret_key == DEFAULT_SECRET_KEY:
        if not allow_insecure_defaults:
            raise RuntimeError(
                'INFINITAS_SERVER_SECRET_KEY must be set to a non-default value when '
                'INFINITAS_SERVER_ENV=production'
            )
        secret_key = DEFAULT_SECRET_KEY

    bootstrap_raw = os.environ.get('INFINITAS_SERVER_BOOTSTRAP_USERS')
    bootstrap_payload = _load_bootstrap_payload(
        bootstrap_raw,
        allow_default_fixture=allow_insecure_defaults,
    )
    bootstrap_users = _normalize_bootstrap_users(bootstrap_payload)
    if not bootstrap_users:
        if not allow_insecure_defaults:
            raise RuntimeError(
                'INFINITAS_SERVER_BOOTSTRAP_USERS must be set to a non-empty JSON array '
                'when INFINITAS_SERVER_ENV=production'
            )
        bootstrap_users = list(DEFAULT_BOOTSTRAP_USERS)

    default_db_path = ROOT / '.state' / 'server.db'
    database_url = os.environ.get('INFINITAS_SERVER_DATABASE_URL') or f'sqlite:///{default_db_path}'
    repo_path = Path(os.environ.get('INFINITAS_SERVER_REPO_PATH') or ROOT).expanduser().resolve()
    artifact_path = Path(os.environ.get('INFINITAS_SERVER_ARTIFACT_PATH') or (ROOT / '.state' / 'artifacts')).expanduser().resolve()
    repo_lock_path = Path(os.environ.get('INFINITAS_SERVER_REPO_LOCK_PATH') or (ROOT / '.state' / 'repo.lock')).expanduser().resolve()
    mirror_remote = str(os.environ.get('INFINITAS_SERVER_MIRROR_REMOTE') or '').strip()
    mirror_branch = str(os.environ.get('INFINITAS_SERVER_MIRROR_BRANCH') or '').strip()

    return Settings(
        app_name='infinitas-hosted-registry',
        root_dir=ROOT,
        environment=environment,
        database_url=database_url,
        secret_key=secret_key,
        template_dir=ROOT / 'server' / 'templates',
        bootstrap_users=bootstrap_users,
        repo_path=repo_path,
        artifact_path=artifact_path,
        repo_lock_path=repo_lock_path,
        mirror_remote=mirror_remote,
        mirror_branch=mirror_branch,
    )
