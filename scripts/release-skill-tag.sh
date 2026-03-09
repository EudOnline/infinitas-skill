#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/release-skill-tag.sh <skill-name-or-path> [--version X.Y.Z] [--create] [--push] [--force] [--unsigned]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
CREATE=0
PUSH=0
FORCE=0
UNSIGNED=0
SET_VERSION=""

resolve_skill() {
  local name="$1"
  if [[ -d "$name" && -f "$name/_meta.json" ]]; then
    printf '%s' "$name"
    return
  fi
  for stage in active incubating archived; do
    if [[ -d "$ROOT/skills/$stage/$name" ]]; then
      printf '%s' "$ROOT/skills/$stage/$name"
      return
    fi
  done
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      SET_VERSION="${2:-}"
      shift 2
      ;;
    --create)
      CREATE=1
      shift
      ;;
    --push)
      PUSH=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --unsigned)
      UNSIGNED=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

DIR="$(resolve_skill "$TARGET")" || { echo "cannot resolve skill: $TARGET" >&2; exit 1; }
readarray -t META < <(python3 - "$DIR/_meta.json" "$SET_VERSION" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    meta = json.load(f)
name = meta['name']
version = sys.argv[2] or meta['version']
status = meta.get('status')
print(name)
print(version)
print(status)
print(meta['version'])
PY
)
NAME="${META[0]}"
VERSION="${META[1]}"
STATUS="${META[2]}"
META_VERSION="${META[3]}"
TAG="skill/$NAME/v$VERSION"

TAG_FORMAT="$(python3 - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
config = json.loads((root / 'config' / 'signing.json').read_text(encoding='utf-8'))
print((config.get('git_tag') or {}).get('format', 'ssh'))
PY
)"
SIGNING_KEY_ENV="$(python3 - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
config = json.loads((root / 'config' / 'signing.json').read_text(encoding='utf-8'))
print((config.get('git_tag') or {}).get('signing_key_env', 'INFINITAS_SKILL_GIT_SIGNING_KEY'))
PY
)"
DEFAULT_REMOTE="$(python3 - "$ROOT" <<'PY'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
config = json.loads((root / 'config' / 'signing.json').read_text(encoding='utf-8'))
print((config.get('git_tag') or {}).get('remote', 'origin'))
PY
)"

signing_key_value() {
  local env_value="${!SIGNING_KEY_ENV:-}"
  if [[ -n "$env_value" ]]; then
    printf '%s' "$env_value"
    return
  fi
  git config --get user.signingkey 2>/dev/null || true
}

ensure_repo_signers() {
  if grep -Eq '^[[:space:]]*[^#[:space:]]' "$ROOT/config/allowed_signers" 2>/dev/null; then
    return 0
  fi
  echo "FAIL: config/allowed_signers has no signer entries; add trusted release signers before creating stable release tags" >&2
  exit 1
}

current_remote() {
  local upstream
  upstream="$(git rev-parse --abbrev-ref @{upstream} 2>/dev/null || true)"
  if [[ -n "$upstream" ]]; then
    printf '%s' "${upstream%%/*}"
    return
  fi
  printf '%s' "$DEFAULT_REMOTE"
}

echo "skill: $NAME"
echo "version: $VERSION"
echo "status: $STATUS"
echo "tag: $TAG"

if [[ $CREATE -eq 1 || $PUSH -eq 1 ]]; then
  python3 "$ROOT/scripts/check-release-state.py" "$DIR" --mode preflight >/dev/null
fi

if [[ $CREATE -eq 1 ]]; then
  if git rev-parse "$TAG" >/dev/null 2>&1; then
    if [[ $FORCE -ne 1 ]]; then
      echo "tag already exists: $TAG (use --force to recreate)" >&2
      exit 1
    fi
    git tag -d "$TAG" >/dev/null
  fi
  if [[ $UNSIGNED -eq 1 ]]; then
    git tag "$TAG"
    echo "created unsigned tag: $TAG"
  else
    ensure_repo_signers
    SIGNING_KEY="$(signing_key_value)"
    if [[ -z "$SIGNING_KEY" ]]; then
      echo "stable release tags are SSH-signed by default; set $SIGNING_KEY_ENV or git config user.signingkey before creating $TAG" >&2
      exit 1
    fi
    GIT_TAG_CMD=(git -c "gpg.format=$TAG_FORMAT")
    if [[ -n "${!SIGNING_KEY_ENV:-}" ]]; then
      GIT_TAG_CMD+=(-c "user.signingkey=${!SIGNING_KEY_ENV}")
    fi
    "${GIT_TAG_CMD[@]}" tag -s "$TAG" -m "$TAG"
    if [[ "$VERSION" == "$META_VERSION" ]]; then
      python3 "$ROOT/scripts/check-release-state.py" "$DIR" --mode local-tag >/dev/null
      echo "created and verified signed tag: $TAG"
    else
      echo "created signed tag: $TAG"
      echo "note: version override bypasses stable-release verification because it differs from _meta.json.version" >&2
    fi
  fi
fi

if [[ $PUSH -eq 1 ]]; then
  REMOTE="$(current_remote)"
  git push "$REMOTE" "refs/tags/$TAG"
  if [[ $UNSIGNED -eq 1 || "$VERSION" != "$META_VERSION" ]]; then
    echo "pushed tag: $TAG"
  else
    python3 "$ROOT/scripts/check-release-state.py" "$DIR" --mode stable-release >/dev/null
    echo "pushed and verified remote tag: $TAG"
  fi
fi
