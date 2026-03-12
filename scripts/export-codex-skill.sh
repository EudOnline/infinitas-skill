#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/export-codex-skill.sh --skill-dir DIR --out DIR" >&2
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
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
skill_dir = Path(sys.argv[2]).resolve()
out_dir = Path(sys.argv[3]).resolve()
sys.path.insert(0, str(root / 'scripts'))

from canonical_skill_lib import load_skill_source  # noqa: E402
from render_skill_lib import load_platform_profile, render_skill  # noqa: E402

source = load_skill_source(skill_dir)
profile = load_platform_profile(root, 'codex')
payload = render_skill(source=source, platform='codex', out_dir=out_dir, profile=profile)
overlay = (source.get('platform_overrides') or {}).get('codex') or {}
files = list(payload.get('files') or [])
if overlay.get('emit_openai_yaml'):
    agents_dir = out_dir / 'agents'
    agents_dir.mkdir(parents=True, exist_ok=True)
    openai_yaml = agents_dir / 'openai.yaml'
    openai_yaml.write_text(
        'name: {}\n'.format(source.get('name')) +
        'description: {}\n'.format(source.get('description')) +
        'entrypoint: SKILL.md\n',
        encoding='utf-8',
    )
    files.append(str(openai_yaml.relative_to(out_dir)))
if overlay.get('emit_agents_md_snippet'):
    agents_md = out_dir / 'AGENTS.md'
    agents_md.write_text(
        '# Codex Skill Bootstrap\n\n'
        f'Load `{source.get("name")}` from `.agents/skills/{source.get("name")}` when its trigger conditions match.\n',
        encoding='utf-8',
    )
    files.append(str(agents_md.relative_to(out_dir)))
payload['files'] = sorted(dict.fromkeys(files))
payload['platform'] = 'codex'
print(json.dumps(payload, ensure_ascii=False))
PY
