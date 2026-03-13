from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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
    database_url: str
    secret_key: str
    template_dir: Path
    bootstrap_users: list[dict]
    repo_path: Path
    artifact_path: Path
    repo_lock_path: Path


def _normalize_bootstrap_users(payload: object) -> list[dict]:
    if not isinstance(payload, list):
        return list(DEFAULT_BOOTSTRAP_USERS)

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
    return normalized or list(DEFAULT_BOOTSTRAP_USERS)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    bootstrap_raw = os.environ.get('INFINITAS_SERVER_BOOTSTRAP_USERS', '')
    try:
        bootstrap_payload = json.loads(bootstrap_raw) if bootstrap_raw else DEFAULT_BOOTSTRAP_USERS
    except json.JSONDecodeError:
        bootstrap_payload = DEFAULT_BOOTSTRAP_USERS

    default_db_path = ROOT / '.state' / 'server.db'
    database_url = os.environ.get('INFINITAS_SERVER_DATABASE_URL') or f'sqlite:///{default_db_path}'
    repo_path = Path(os.environ.get('INFINITAS_SERVER_REPO_PATH') or ROOT).expanduser().resolve()
    artifact_path = Path(os.environ.get('INFINITAS_SERVER_ARTIFACT_PATH') or (ROOT / '.state' / 'artifacts')).expanduser().resolve()
    repo_lock_path = Path(os.environ.get('INFINITAS_SERVER_REPO_LOCK_PATH') or (ROOT / '.state' / 'repo.lock')).expanduser().resolve()

    return Settings(
        app_name='infinitas-hosted-registry',
        root_dir=ROOT,
        database_url=database_url,
        secret_key=os.environ.get('INFINITAS_SERVER_SECRET_KEY', 'change-me'),
        template_dir=ROOT / 'server' / 'templates',
        bootstrap_users=_normalize_bootstrap_users(bootstrap_payload),
        repo_path=repo_path,
        artifact_path=artifact_path,
        repo_lock_path=repo_lock_path,
    )
