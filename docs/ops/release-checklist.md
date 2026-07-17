---
audience: operators and release maintainers
owner: repository maintainers
source_of_truth: release checklist
last_reviewed: 2026-04-08
status: maintained
---

# Release / Promote Checklist

Before pushing or promoting a skill:

- [ ] Folder name is lowercase-hyphen format
- [ ] `SKILL.md` has `name` and `description`
- [ ] `name:` matches the folder name
- [ ] `_meta.json` exists and `uv run infinitas policy check-promotion <name> --as-active --json` passes
- [ ] full registry validation passes via `scripts/check-all.sh`
- [ ] `_meta.json.status` matches the parent directory
- [ ] computed review quorum passes for the target stage via `uv run infinitas policy review-status <name> --as-active --require-pass`
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
- [ ] `uv run infinitas registry catalog build` has been run after metadata changes

Before creating stable release output for an active skill:

- [ ] if upstream OpenClaw behavior changed, or if historical Codex / Claude compatibility claims need refreshing, follow `docs/ops/platform-drift-playbook.md` before starting release work
- [ ] trusted signer bootstrap was completed with `uv run infinitas release bootstrap-signing ...` or an equivalent existing-key flow from `docs/ops/signing-bootstrap.md`
- [ ] `config/allowed_signers` contains at least one trusted release signer entry committed in-repo
- [ ] publisher `authorized_signers` / `authorized_releasers` policy was updated when the release uses a qualified publisher namespace
- [ ] `uv run infinitas release doctor-signing <name>` has no `FAIL` items before the first stable tag
- [ ] `git status --short` is empty for the repository worktree
- [ ] current branch tracks its upstream and is neither ahead nor behind it
- [ ] expected tag `skill/<name>/v<version>` does not already point at the wrong commit
- [ ] default stable tag is created with `uv run infinitas release tag <name> --create --push`
- [ ] `uv run infinitas release check-state <name> --mode preflight --json` passes before writing notes, provenance, or GitHub releases
- [ ] `uv run infinitas release check-state <name> --mode preflight --json` shows `release.platform_compatibility.canonical_runtime_platform = "openclaw"`
- [ ] `uv run infinitas release check-state <name> --mode preflight --json` shows `release.platform_compatibility.blocking_platforms = []` for the canonical OpenClaw runtime
- [ ] if delegated reviewer groups, delegated publisher teams, or break-glass waivers are involved, `uv run infinitas release check-state <name> --mode preflight --json` shows the expected `review.latest_decisions`, `review.ignored_decisions`, `release.delegated_teams`, and `release.exception_usage`
- [ ] any command that writes release notes or distribution output also includes `--write-provenance` while the v9 attestation policy is enabled
- [ ] release notes or provenance reference `refs/tags/skill/<name>/v<version>` instead of local-only `HEAD`
- [ ] `catalog/provenance/<name>-<version>.json` records the resolved registry context, dependency plan, and attestation signer identity
- [ ] when delegated approvals or release exceptions were used, `catalog/provenance/<name>-<version>.json` preserves that audit context in `review.*` and `release.*` instead of relying on a separate export artifact
- [ ] `uv run infinitas release verify-attestation catalog/provenance/<name>-<version>.json --json` passes against repo-managed allowed signers
- [ ] if CI attestation / CI-native attestation is enabled, `catalog/provenance/<name>-<version>.ci.json` was generated and `uv run infinitas release verify-ci-attestation ... --json` passes
- [ ] `config/signing.json` `attestation.policy.release_trust_mode` matches the intended rollout mode; the key `release_trust_mode` is set to `ssh`, `ci`, or `both`
- [ ] `uv run infinitas release doctor-signing <name> --provenance catalog/provenance/<name>-<version>.json` reports no blocking failures after the rehearsal
- [ ] any optional legacy HMAC provenance signing happens after the required SSH attestation has already been verified
- [ ] fresh OpenClaw evidence exists under `catalog/compatibility-evidence/openclaw/<name>/<version>.json` before a stable release if runtime behavior or platform contracts changed
- [ ] if Codex or Claude support is declared, corresponding current evidence exists under `catalog/compatibility-evidence/<platform>/<name>/<version>.json`
- [ ] if `release.platform_compatibility.canonical_runtime.freshness_state = stale|unknown`, refresh the evidence and rerun the playbook steps in `docs/ops/platform-drift-playbook.md`

When the hosted control plane performs the release:

- [ ] skill and immutable version creation were authorized for the owning principal
- [ ] the Agent/CLI uploaded a complete bundle and used the returned one-use `content_id`
- [ ] the uploaded root slug and `_meta.json.version` match the Skill and requested version
- [ ] the release creates exactly one `materialize_release` job
- [ ] the worker writes manifest, bundle, provenance, and signature artifacts into the configured artifact directory
- [ ] the worker reruns the formal installable-Skill validator before the release reaches `ready`
- [ ] API, provenance, and manifest preserve the same platform compatibility result
- [ ] exposure activation and review decisions are recorded separately from release materialization
- [ ] if a one-way mirror is required, run `uv run infinitas registry sources mirror` after successful materialization
- [ ] audit events link version creation, release creation, exposure decisions, and access issuance
