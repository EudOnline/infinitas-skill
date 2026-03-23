#!/usr/bin/env bash
set -euo pipefail

: "${INFINITAS_SERVER_REPO_PATH:=/srv/infinitas/repo}"
: "${INFINITAS_SERVER_ARTIFACT_PATH:=/srv/infinitas/artifacts}"
: "${INFINITAS_SERVER_REPO_LOCK_PATH:=/srv/infinitas/data/repo.lock}"
: "${INFINITAS_SERVER_DATABASE_URL:=sqlite:////srv/infinitas/data/server.db}"
: "${HOME:=/srv/infinitas/home}"

if [[ ! -d "$INFINITAS_SERVER_REPO_PATH" ]]; then
  echo "missing hosted repo checkout: $INFINITAS_SERVER_REPO_PATH" >&2
  exit 1
fi

if ! git -C "$INFINITAS_SERVER_REPO_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "hosted repo path is not a git worktree: $INFINITAS_SERVER_REPO_PATH" >&2
  exit 1
fi

mkdir -p "$HOME"

python3 - <<'PY'
import os
from pathlib import Path

from server.artifact_ops import sync_catalog_artifacts

database_url = os.environ.get('INFINITAS_SERVER_DATABASE_URL', '')
if database_url.startswith('sqlite:///'):
    db_path = Path(database_url.removeprefix('sqlite:///')).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

artifact_path = Path(os.environ['INFINITAS_SERVER_ARTIFACT_PATH']).expanduser().resolve()
artifact_path.mkdir(parents=True, exist_ok=True)

repo_lock_path = os.environ.get('INFINITAS_SERVER_REPO_LOCK_PATH', '')
if repo_lock_path:
    Path(repo_lock_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

sync_catalog_artifacts(Path(os.environ['INFINITAS_SERVER_REPO_PATH']), artifact_path)
PY

exec "$@"
