#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: scripts/verify-provenance-ssh.sh <provenance-json> [--identity NAME] [--allowed-signers PATH] [--namespace NAME]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="$1"
shift || true
VERIFY_ARGS=(python3 "$ROOT/scripts/verify-attestation.py" "$FILE")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --identity)
      VERIFY_ARGS+=(--identity "${2:-}")
      shift 2
      ;;
    --allowed-signers)
      VERIFY_ARGS+=(--allowed-signers "${2:-}")
      shift 2
      ;;
    --namespace)
      VERIFY_ARGS+=(--namespace "${2:-}")
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

"${VERIFY_ARGS[@]}"
