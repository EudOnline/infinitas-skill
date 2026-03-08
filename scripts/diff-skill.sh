#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: scripts/diff-skill.sh <skill-a> <skill-b>" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
resolve_skill() {
  local name="$1"
  if [[ -d "$name" ]]; then
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

A="$(resolve_skill "$1")" || { echo "cannot resolve skill: $1" >&2; exit 1; }
B="$(resolve_skill "$2")" || { echo "cannot resolve skill: $2" >&2; exit 1; }

diff -ru "$A" "$B" || true
