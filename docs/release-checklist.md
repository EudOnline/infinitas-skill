# Release / Promote Checklist

Before pushing or promoting a skill:

- [ ] Folder name is lowercase-hyphen format
- [ ] `SKILL.md` has `name` and `description`
- [ ] `name:` matches the folder name
- [ ] `_meta.json` exists and passes `scripts/check-skill.sh`
- [ ] full registry validation passes via `scripts/check-all.sh`
- [ ] `_meta.json.status` matches the parent directory
- [ ] `_meta.json.review_state` is appropriate for the target stage
- [ ] `_meta.json.version` was bumped appropriately for behavioral changes
- [ ] `CHANGELOG.md` was updated
- [ ] Trigger description clearly states when the skill should activate
- [ ] Long reference material is stored under `references/`
- [ ] Helper code lives under `scripts/`
- [ ] Output resources live under `assets/`
- [ ] `tests/smoke.md` exists and was read by a human reviewer
- [ ] No tokens, API keys, cookies, or auth exports are committed
- [ ] Skill was manually tested on at least one realistic task
- [ ] `scripts/build-catalog.sh` has been run after metadata changes
