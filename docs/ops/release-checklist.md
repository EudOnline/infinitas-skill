---
audience: operators and release maintainers
owner: repository maintainers
source_of_truth: release checklist
last_reviewed: 2026-03-30
status: maintained
---

# Release / Promote Checklist

Before pushing or promoting a skill:

- [ ] Folder name is lowercase-hyphen format
- [ ] `SKILL.md` has `name` and `description`
- [ ] `name:` matches the folder name
- [ ] `_meta.json` exists and passes `scripts/check-skill.sh`
- [ ] full registry validation passes via `scripts/check-all.sh`
- [ ] `_meta.json.status` matches the parent directory
- [ ] computed review quorum passes for the target stage via `scripts/review-status.py <name> --as-active --require-pass`
- [ ] if this is a solo-maintainer repo, confirm `policy/promotion-policy.json` intentionally enables `reviews.allow_owner_when_no_distinct_reviewer` before relying on owner approval fallback
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

- [ ] if upstream Codex / Claude Code / OpenClaw behavior changed, follow `docs/ops/platform-drift-playbook.md` before starting release work
- [ ] trusted signer bootstrap was completed with `python3 scripts/bootstrap-signing.py ...` or an equivalent existing-key flow from `docs/ops/signing-bootstrap.md`
- [ ] `config/allowed_signers` contains at least one trusted release signer entry committed in-repo
- [ ] publisher `authorized_signers` / `authorized_releasers` policy was updated when the release uses a qualified publisher namespace
- [ ] `python3 scripts/doctor-signing.py <name>` has no `FAIL` items before the first stable tag
- [ ] `git status --short` is empty for the repository worktree
- [ ] current branch tracks its upstream and is neither ahead nor behind it
- [ ] expected tag `skill/<name>/v<version>` does not already point at the wrong commit
- [ ] default stable tag is created with `scripts/release-skill.sh <name> --push-tag` or `scripts/release-skill-tag.sh <name> --create --push`
- [ ] `uv run infinitas release check-state <name> --mode preflight --json` passes before writing notes, provenance, or GitHub releases
- [ ] `uv run infinitas release check-state <name> --mode preflight --json` shows `release.platform_compatibility.blocking_platforms = []` for every declared platform
- [ ] if delegated reviewer groups, delegated publisher teams, or break-glass waivers are involved, `uv run infinitas release check-state <name> --mode preflight --json` shows the expected `review.latest_decisions`, `review.ignored_decisions`, `release.delegated_teams`, and `release.exception_usage`
- [ ] any command that writes release notes or distribution output also includes `--write-provenance` while the v9 attestation policy is enabled
- [ ] release notes or provenance reference `refs/tags/skill/<name>/v<version>` instead of local-only `HEAD`
- [ ] `catalog/provenance/<name>-<version>.json` records the resolved registry context, dependency plan, and attestation signer identity
- [ ] when delegated approvals or release exceptions were used, `catalog/provenance/<name>-<version>.json` preserves that audit context in `review.*` and `release.*` instead of relying on a separate export artifact
- [ ] `scripts/verify-attestation.py catalog/provenance/<name>-<version>.json` passes against repo-managed allowed signers
- [ ] if CI attestation / CI-native attestation is enabled, `catalog/provenance/<name>-<version>.ci.json` was generated and `python3 scripts/verify-ci-attestation.py ...` passes
- [ ] `config/signing.json` `attestation.policy.release_trust_mode` matches the intended rollout mode; the key `release_trust_mode` is set to `ssh`, `ci`, or `both`
- [ ] `python3 scripts/doctor-signing.py <name> --provenance catalog/provenance/<name>-<version>.json` reports no blocking failures after the rehearsal
- [ ] any optional legacy HMAC provenance signing happens after the required SSH attestation has already been verified
- [ ] platform evidence was refreshed with `python3 scripts/record-verified-support.py <name> --platform codex --platform claude --platform openclaw --build-catalog` if verified compatibility claims changed
- [ ] if any declared platform shows `freshness_state = stale|unknown`, refresh the evidence and rerun the playbook steps in `docs/ops/platform-drift-playbook.md`

When the hosted control plane performs the release:

- [ ] queued jobs were created by a maintainer-authorized action and linked back to the reviewed submission
- [ ] the server-owned repo checkout is locked for exclusive mutation during validate / promote / publish
- [ ] validation job materializes the submitted skill into `skills/incubating/` and commits the exact reviewed payload
- [ ] promotion job commits and pushes the `skills/incubating/` → `skills/active/` move before publish begins
- [ ] publish job syncs `catalog/`, `catalog/provenance/`, and immutable distribution outputs into the hosted artifact directory after release succeeds
- [ ] if `INFINITAS_SERVER_MIRROR_REMOTE` is configured, the publish job log shows either a successful one-way mirror command or an explicit warning reviewed by the operator
- [ ] job logs capture every invoked script so operators can audit validate / promote / publish execution
