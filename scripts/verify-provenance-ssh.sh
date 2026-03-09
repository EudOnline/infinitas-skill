#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/verify-provenance-ssh.sh <provenance-json> --identity NAME [--allowed-signers PATH] [--namespace NAME]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$1"
shift || true
IDENTITY=""
ALLOWED="$(python3 - <<'PY' "$ROOT"
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
print((root / json.loads((root/'config'/'signing.json').read_text(encoding='utf-8')).get('allowed_signers','config/allowed_signers')).resolve())
PY
)"
NAMESPACE="$(python3 - <<'PY' "$ROOT"
import json, sys
from pathlib import Path
root=Path(sys.argv[1])
print(json.loads((root/'config'/'signing.json').read_text(encoding='utf-8')).get('namespace','infinitas-skill'))
PY
)"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --identity)
      IDENTITY="${2:-}"
      shift 2
      ;;
    --allowed-signers)
      ALLOWED="${2:-}"
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
[[ -n "$IDENTITY" ]] || { echo "--identity is required" >&2; exit 1; }
if ! grep -Eq '^[[:space:]]*[^#[:space:]]' "$ALLOWED" 2>/dev/null; then
  echo "allowed signers file has no trusted entries: $ALLOWED" >&2
  exit 1
fi
SIG="$FILE.ssig"
[[ -f "$SIG" ]] || { echo "missing SSH signature: $SIG" >&2; exit 1; }
ssh-keygen -Y verify -f "$ALLOWED" -I "$IDENTITY" -n "$NAMESPACE" -s "$SIG" < "$FILE"
