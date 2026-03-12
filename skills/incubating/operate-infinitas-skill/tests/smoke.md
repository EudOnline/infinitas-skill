# Smoke test

Scenario:

The user says: "I have an OpenClaw prototype in `~/.openclaw/workspace/skills/demo-skill`. Import it into this repo, get it ready for review, publish a stable version, then tell another agent how to install it."

Expected behavior:

- identify the four repository states before choosing commands
- use `scripts/import-openclaw-skill.sh` for the prototype ingest
- use `scripts/check-skill.sh` plus the review flow before release
- use `scripts/publish-skill.sh` to create the immutable release
- instruct the second agent to use `scripts/pull-skill.sh`, not a direct copy from `skills/incubating/` or `skills/active/`
