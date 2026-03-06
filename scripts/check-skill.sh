#!/usr/bin/env bash
set -euo pipefail

DIR="${1:-}"
if [[ -z "$DIR" ]]; then
  echo "usage: scripts/check-skill.sh <skill-dir>" >&2
  exit 1
fi

[[ -d "$DIR" ]] || { echo "missing directory: $DIR" >&2; exit 1; }
[[ -f "$DIR/SKILL.md" ]] || { echo "missing SKILL.md in $DIR" >&2; exit 1; }

STATUS=0
BASENAME="$(basename "$DIR")"
NAME_LINE="$(sed -n 's/^name: //p' "$DIR/SKILL.md" | head -n 1)"
DESC_LINE="$(sed -n 's/^description: //p' "$DIR/SKILL.md" | head -n 1)"

if [[ -z "$NAME_LINE" ]]; then
  echo "FAIL: missing name field" >&2
  STATUS=1
fi
if [[ -z "$DESC_LINE" ]]; then
  echo "FAIL: missing description field" >&2
  STATUS=1
fi
if [[ -n "$NAME_LINE" && "$NAME_LINE" != "$BASENAME" ]]; then
  echo "WARN: folder name ($BASENAME) does not match name field ($NAME_LINE)" >&2
fi

if grep -RInE '(gh[pousr]_|github_pat_|sk-[A-Za-z0-9_-]{10,}|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-|-----BEGIN (RSA|OPENSSH|EC|DSA|PGP|PRIVATE KEY)|Authorization:[[:space:]]*Bearer[[:space:]]+[A-Za-z0-9._-]+)' "$DIR" >/tmp/skill-check-secrets.$$ 2>/dev/null; then
  echo "FAIL: possible secrets detected" >&2
  sed -n '1,20p' /tmp/skill-check-secrets.$$ >&2
  STATUS=1
fi
rm -f /tmp/skill-check-secrets.$$

if [[ $STATUS -eq 0 ]]; then
  echo "OK: $DIR"
fi
exit $STATUS
