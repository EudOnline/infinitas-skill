#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/export-claude-skill.sh --skill-dir DIR --out DIR" >&2
}

SKILL_DIR=""
OUT_DIR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill-dir)
      SKILL_DIR="${2:-}"
      shift 2
      ;;
    --out)
      OUT_DIR="${2:-}"
      shift 2
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

[[ -n "$SKILL_DIR" && -n "$OUT_DIR" ]] || { usage; exit 1; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT" "$SKILL_DIR" "$OUT_DIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
skill_dir = Path(sys.argv[2]).resolve()
out_dir = Path(sys.argv[3]).resolve()
sys.path.insert(0, str(root / 'scripts'))

from canonical_skill_lib import load_skill_source  # noqa: E402
from render_skill_lib import load_platform_profile, render_skill  # noqa: E402

source = load_skill_source(skill_dir)
profile = load_platform_profile(root, 'claude')
payload = render_skill(source=source, platform='claude', out_dir=out_dir, profile=profile)
overlay = (source.get('platform_overrides') or {}).get('claude') or {}
files = list(payload.get('files') or [])
command_wrapper_name = overlay.get('command_wrapper_name')
if command_wrapper_name:
    commands_dir = out_dir / 'commands'
    commands_dir.mkdir(parents=True, exist_ok=True)
    wrapper = commands_dir / f'{command_wrapper_name}.md'
    wrapper.write_text(
        '---\n'
        f'description: "Wrapper for {source.get("name")}"\n'
        '---\n\n'
        f'Use the `{source.get("name")}` skill when this command is invoked.\n',
        encoding='utf-8',
    )
    files.append(str(wrapper.relative_to(out_dir)))
payload['files'] = sorted(dict.fromkeys(files))
payload['platform'] = 'claude'
print(json.dumps(payload, ensure_ascii=False))
PY
