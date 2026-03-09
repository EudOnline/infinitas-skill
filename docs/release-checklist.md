# Release / Promote Checklist

Before pushing or promoting a skill:

- [ ] Folder name is lowercase-hyphen format
- [ ] `SKILL.md` has `name` and `description`
- [ ] `name:` matches the folder name
- [ ] `_meta.json` exists and passes `scripts/check-skill.sh`
- [ ] full registry validation passes via `scripts/check-all.sh`
- [ ] `_meta.json.status` matches the parent directory
- [ ] computed review quorum passes for the target stage via `scripts/review-status.py <name> --as-active --require-pass`
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

Before creating stable release output for an active skill:

- [ ] `config/allowed_signers` contains at least one trusted release signer entry committed in-repo
- [ ] `git status --short` is empty for the repository worktree
- [ ] current branch tracks its upstream and is neither ahead nor behind it
- [ ] expected tag `skill/<name>/v<version>` does not already point at the wrong commit
- [ ] default stable tag is created with `scripts/release-skill.sh <name> --push-tag` or `scripts/release-skill-tag.sh <name> --create --push`
- [ ] `scripts/check-release-state.py <name>` passes before writing notes, provenance, or GitHub releases
- [ ] release notes or provenance reference `refs/tags/skill/<name>/v<version>` instead of local-only `HEAD`
- [ ] any optional provenance signing happens after the signed git tag has already been verified
