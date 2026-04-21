# Smoke test

Scenario:

"Find the best released skill for installing into OpenClaw, inspect the trust state first, then preview the immutable install plan before writing anything to `~/.openclaw/skills`."

Expected guidance:

- use `uv run infinitas discovery search` or `uv run infinitas discovery recommend`
- inspect with `uv run infinitas discovery inspect`
- preview with `scripts/pull-skill.sh ... --mode confirm` or `uv run infinitas install by-name ... --mode confirm --json`
- only install or upgrade from immutable release artifacts
