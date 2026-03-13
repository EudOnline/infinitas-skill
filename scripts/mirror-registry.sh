#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/mirror-registry.sh --remote <name> [--branch <name>] [--dry-run] [--fetch|--pull|--reverse-sync forbidden]" >&2
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE=""
BRANCH=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote)
      REMOTE="${2:-}"
      shift 2
      ;;
    --branch)
      BRANCH="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --fetch|--pull|--reverse-sync)
      echo "reverse sync is forbidden for hosted registry mirrors: $1" >&2
      exit 1
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

[[ -n "$REMOTE" ]] || { usage; exit 1; }

cd "$ROOT"

git remote get-url "$REMOTE" >/dev/null 2>&1 || {
  echo "missing remote: $REMOTE" >&2
  exit 1
}

if [[ -n "$(git status --short)" ]]; then
  echo "source-of-truth repo is dirty; commit or stash changes before mirroring" >&2
  exit 1
fi

if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git branch --show-current)"
fi

[[ -n "$BRANCH" ]] || {
  echo "could not determine branch to mirror" >&2
  exit 1
}

PUSH_BRANCH_CMD=(git push "$REMOTE" "refs/heads/$BRANCH:refs/heads/$BRANCH")
PUSH_TAGS_CMD=(git push "$REMOTE" --tags)

echo "one-way mirror: $ROOT -> remote $REMOTE"
echo "branch: $BRANCH"
echo "tags: all local tags"
echo "\$ ${PUSH_BRANCH_CMD[*]}"
echo "\$ ${PUSH_TAGS_CMD[*]}"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "dry-run only; no refs were pushed"
  exit 0
fi

"${PUSH_BRANCH_CMD[@]}"
"${PUSH_TAGS_CMD[@]}"
echo "mirror push completed"
