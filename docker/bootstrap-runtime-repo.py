#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from server.artifact_ops import sync_catalog_artifacts
from server.runtime_repo import ensure_runtime_repo


def _env_flag(name: str) -> bool:
    value = str(os.environ.get(name, '')).strip().lower()
    return value in {'1', 'true', 'yes', 'on'}


def main() -> int:
    repo_path = Path(os.environ.get('INFINITAS_SERVER_REPO_PATH') or '/srv/infinitas/repo')
    bundled_repo_path = Path(os.environ.get('INFINITAS_BUNDLED_REPO_PATH') or '/opt/infinitas/bundle')
    repo_lock_path = Path(os.environ.get('INFINITAS_SERVER_REPO_LOCK_PATH') or '/srv/infinitas/data/repo.lock')
    artifact_path = Path(os.environ.get('INFINITAS_SERVER_ARTIFACT_PATH') or '/srv/infinitas/artifacts')
    branch = str(os.environ.get('INFINITAS_SERVER_GIT_BRANCH') or 'main').strip() or 'main'
    origin_url = str(os.environ.get('INFINITAS_SERVER_GIT_ORIGIN_URL') or '').strip()
    git_user_name = str(os.environ.get('INFINITAS_SERVER_GIT_USER_NAME') or 'Infinitas Hosted Registry').strip()
    git_user_email = str(os.environ.get('INFINITAS_SERVER_GIT_USER_EMAIL') or 'hosted-registry@example.com').strip()

    result = ensure_runtime_repo(
        bundled_repo_path=bundled_repo_path,
        repo_path=repo_path,
        repo_lock_path=repo_lock_path,
        branch=branch,
        origin_url=origin_url,
        git_user_name=git_user_name or 'Infinitas Hosted Registry',
        git_user_email=git_user_email or 'hosted-registry@example.com',
        allow_reset=_env_flag('INFINITAS_SERVER_REPO_BOOTSTRAP_RESET'),
    )

    artifact_path.mkdir(parents=True, exist_ok=True)
    sync_catalog_artifacts(repo_path, artifact_path)

    print(
        json.dumps(
            {
                'ok': True,
                'seeded': result.seeded,
                'repo_path': str(result.repo_path),
                'branch': result.branch,
                'origin_configured': result.origin_configured,
                'artifact_path': str(artifact_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
