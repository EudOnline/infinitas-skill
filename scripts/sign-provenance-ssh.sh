#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/sign-provenance-ssh.sh <provenance-json> --key PATH [--namespace NAME]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$1"
shift || true
KEY=""
NAMESPACE="$(python3 - <<'PY' "$ROOT"
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
print(json.loads((root/'config'/'signing.json').read_text(encoding='utf-8')).get('namespace','infinitas-skill'))
PY
)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --key)
      KEY="${2:-}"
      shift 2
      ;;
    --namespace)
      NAMESPACE="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done
[[ -n "$KEY" ]] || { echo "--key is required" >&2; exit 1; }
ssh-keygen -Y sign -f "$KEY" -n "$NAMESPACE" "$FILE" >/dev/null
SIG="$FILE.ssig"
if [[ -f "$FILE.sig" ]]; then
  mv "$FILE.sig" "$SIG"
fi
echo "$SIG"
