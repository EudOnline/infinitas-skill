#!/usr/bin/env bash
set -euo pipefail

: "${INFINITAS_BUNDLED_REPO_PATH:=/opt/infinitas/bundle}"
: "${INFINITAS_SERVER_REPO_PATH:=/srv/infinitas/repo}"
: "${INFINITAS_SERVER_ARTIFACT_PATH:=/srv/infinitas/artifacts}"
: "${INFINITAS_SERVER_REPO_LOCK_PATH:=/srv/infinitas/data/repo.lock}"
: "${INFINITAS_SERVER_DATABASE_URL:=sqlite:////srv/infinitas/data/server.db}"
: "${HOME:=/srv/infinitas/home}"

mkdir -p "$HOME"
python3 "$INFINITAS_BUNDLED_REPO_PATH/docker/bootstrap-runtime-repo.py" >/tmp/infinitas-bootstrap-runtime-repo.json
cat /tmp/infinitas-bootstrap-runtime-repo.json

exec "$@"
