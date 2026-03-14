#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/inspect-skill.sh <qualified-or-name> [--version X.Y.Z]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="$1"
shift || true
VERSION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

python3 - <<'PY' "$ROOT" "$NAME" "$VERSION"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'scripts'))
from search_inspect_lib import inspect_skill  # noqa: E402

print(json.dumps(inspect_skill(root, name=sys.argv[2], version=sys.argv[3] or None), ensure_ascii=False))
PY
