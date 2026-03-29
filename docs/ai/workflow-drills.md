# Workflow Drills

Use this short drill when a caller needs a private-first recommendation and you want to verify the result before mutating a local runtime.

## Recommended drill

1. Search for candidates with `scripts/search-skills.sh`.
2. Ask for the best-ranked fit with `scripts/recommend-skill.sh`.
3. Inspect the chosen release with `scripts/inspect-skill.sh`.
4. Preview install or upgrade with `--mode confirm` before applying changes.

## Example

```bash
scripts/search-skills.sh operate
scripts/recommend-skill.sh "Need a codex skill for repository operations"
scripts/inspect-skill.sh lvxiaoer/operate-infinitas-skill
scripts/install-by-name.sh operate-infinitas-skill ~/.openclaw/skills --mode confirm
```
