# Smoke test

Scenario:

"Find the best released skill for installing into OpenClaw, inspect the trust state first, then preview the immutable install plan before writing anything to `~/.openclaw/skills`."

Expected guidance:

- use `scripts/search-skills.sh` or `scripts/recommend-skill.sh`
- inspect with `scripts/inspect-skill.sh`
- preview with `scripts/pull-skill.sh ... --mode confirm` or `scripts/install-by-name.sh ... --mode confirm`
- only install or upgrade from immutable release artifacts
