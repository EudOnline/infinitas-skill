# Codebase Concerns

Snapshot date: 2026-03-08

This repository already has solid governance intent, but several of the highest-risk paths are still policy-by-convention rather than policy-by-enforcement. For v9 planning, the main theme is to make registry source selection, review identity, signing, and release outputs immutable and machine-verifiable before the project adds more registries or more automation.

## What v9 should prioritize first

1. Make registry syncing safe and immutable.
2. Turn review/quorum from editable JSON into enforceable repository controls.
3. Make release outputs reproducible, signed by default, and tied to immutable refs.
4. Add end-to-end tests for install/sync/promote/release against fixture skills and a fixture remote registry.

## Critical concerns

### 1. `sync-all-registries` can hard-reset the working tree

- Severity: Critical
- Evidence:
  - `config/registry-sources.json:3` sets the default `self` registry as `kind: "git"` with `local_path: "."`.
  - `scripts/sync-all-registries.sh:10` iterates every enabled registry, including `self`.
  - `scripts/sync-registry-source.sh:55` to `scripts/sync-registry-source.sh:58` runs `git fetch`, `checkout -B`, and `reset --hard` against the resolved registry path.
- Why this matters:
  - In the current config, syncing `self` targets the repository root itself, not an isolated cache.
  - On this checkout, local `main` is ahead of `origin/main` by two commits and there are no release tags yet, so running `scripts/sync-all-registries.sh` would reset local branch state back to `origin/main` and discard local-only history unless recovered from reflog.
  - This is both a fragility issue and a release consistency issue: the same repository is acting as source-of-truth, working tree, and sync target.
- v9 action:
  - Separate mutable worktrees from immutable registry caches.
  - Disallow `git` registries whose `local_path` points at the active repo root.
  - Require sync to operate only on detached cache clones or pinned commits.

### 2. Registry trust is descriptive only; remote resolution is not integrity-enforced

- Severity: High
- Evidence:
  - `scripts/check-registry-sources.py:38` only checks that `trust` is a non-empty string.
  - `scripts/resolve-skill-source.py:76` to `scripts/resolve-skill-source.py:83` sorts candidates by registry priority, stage, snapshot timestamp, and directory name; `registry_trust` is collected but never used to gate resolution.
  - `scripts/sync-registry-source.sh:46` to `scripts/sync-registry-source.sh:62` clones or fast-forwards a branch head, not a pinned commit, signed tag, or allowlisted digest.
  - `.github/workflows/validate.yml:12` and `.github/workflows/validate.yml:15` use marketplace action tags (`@v4`, `@v5`) rather than pinned SHAs.
- Why this matters:
  - The repo already models multiple registries, but a future higher-priority registry could win resolution without any cryptographic verification or trust-policy enforcement.
  - Branch-head based sync means the exact content selected for install is time-variant.
  - The current supply-chain model depends on repo configuration discipline, not verifiable provenance.
- v9 action:
  - Add host allowlists, registry trust tiers with enforcement, and commit/tag pinning.
  - Verify signed tags or signed commits before syncing or resolving a remote registry.
  - Pin GitHub Actions by commit SHA and add explicit workflow permissions.

## Governance and review concerns

### 3. Review/quorum is editable state, not authenticated state

- Severity: High
- Evidence:
  - `scripts/request-review.sh:51` mutates `_meta.json.review_state` to `under-review` directly.
  - `scripts/approve-skill.sh:69` to `scripts/approve-skill.sh:77` appends reviewer decisions to `reviews.json` and flips `_meta.json.review_state` to `approved` or `rejected` immediately.
  - `scripts/check-promotion-policy.py:53` to `scripts/check-promotion-policy.py:57` enforces approval count and rejection blocking only when the policy script is run.
  - There is no `CODEOWNERS` file in the repository, and `.github/workflows/validate.yml` only runs validation; it does not enforce reviewer identity or quorum at merge time.
- Why this matters:
  - Any contributor with write access can claim any reviewer name in `reviews.json`.
  - `_meta.json.review_state` can say `approved` even when quorum has not actually been met.
  - The governance model is auditable, but not authoritative.
- v9 action:
  - Treat `reviews.json` as an audit log only; derive effective review state from signed or platform-authenticated approvals.
  - Add CODEOWNERS and repository-side branch protection / required checks.
  - Make promotion consume computed quorum state, not mutable metadata.

### 4. Promotion and review status can diverge from actual readiness

- Severity: Medium
- Evidence:
  - `scripts/approve-skill.sh:75` sets `review_state` based on the most recent single decision.
  - `scripts/promote-skill.sh:40` to `scripts/promote-skill.sh:46` checks `review_state == approved` and then separately runs policy enforcement.
  - `scripts/build-catalog.sh:55` includes `review_state`, `approval_count`, and `rejection_count` in generated catalogs, so downstream consumers can observe a misleading intermediate state.
- Why this matters:
  - The repository already knows how to compute quorum, but still stores and exports a mutable summary field that can drift.
  - This is likely to create operator confusion once real skills and multiple reviewers exist.
- v9 action:
  - Replace stored `review_state` with a derived field during catalog build and release.
  - Introduce a single source of truth for approval state.

## Signing and attestation concerns

### 5. Provenance signing exists, but it is optional, partially unverifiable, and not release-blocking

- Severity: High
- Evidence:
  - `scripts/release-skill.sh:181` to `scripts/release-skill.sh:200` only signs or verifies provenance when optional flags are provided.
  - `scripts/sign-provenance.py:15` to `scripts/sign-provenance.py:31` uses a shared HMAC secret from `INFINITAS_SKILL_SIGNING_KEY`, which is symmetric and not reviewer-attributable.
  - `config/allowed_signers` is empty, while `scripts/verify-provenance-ssh.sh:13` to `scripts/verify-provenance-ssh.sh:18` defaults to that file for SSH verification.
  - `scripts/generate-provenance.py:33` to `scripts/generate-provenance.py:51` records skill metadata plus git repo/branch/commit, but not the full file manifest, registry source commit, dependency graph, builder identity, workflow run identity, or dirty-worktree state.
- Why this matters:
  - HMAC signing proves shared-secret possession, not which individual approved or produced a release.
  - SSH signing support is present, but the default verifier configuration is not usable yet.
  - Release provenance is informative, but not a strong attestation artifact.
- v9 action:
  - Make SSH or Sigstore-style asymmetric signing the default, not the exception.
  - Populate and manage `config/allowed_signers` as part of the repository bootstrap.
  - Expand provenance to include source registry identity, resolved commit, file/tree digests, dependency resolution, signer identity, and CI run metadata.

## Release consistency concerns

### 6. Releases are not guaranteed to correspond to an immutable, pushed, clean source state

- Severity: High
- Evidence:
  - `scripts/release-skill.sh:102` to `scripts/release-skill.sh:103` validates current working tree content, but does not require a clean git status or a synchronized upstream state.
  - `scripts/generate-provenance.py:24` to `scripts/generate-provenance.py:28` records only `HEAD` commit and current branch, not whether the worktree was dirty.
  - `scripts/release-skill.sh:163` to `scripts/release-skill.sh:179` makes tag creation and tag push optional.
  - `docs/release-strategy.md:49` and `docs/release-strategy.md:50` treat tagging as optional guidance, not a required invariant.
  - The current repository has no git tags, even though release/tag helpers exist.
- Why this matters:
  - A release summary or provenance file can be generated from uncommitted changes while still pointing at the previous `HEAD` commit.
  - Local-only tags or local-only commits can make one machine believe a release exists while every other consumer sees a different registry state.
- v9 action:
  - Require clean worktree, pushed commit, and pushed signed tag before a release is considered valid.
  - Fail release if provenance is not generated and verified.
  - Promote a single release command that emits an immutable bundle rather than many optional steps.

### 7. Catalog outputs are not emitted as one coherent snapshot

- Severity: High
- Evidence:
  - `scripts/build-catalog.sh:115` to `scripts/build-catalog.sh:122` only rewrites a catalog file when its normalized content changes.
  - Current outputs already show different `generated_at` values: `catalog/catalog.json` and `catalog/active.json` are `2026-03-08T03:21:40Z`, `catalog/compatibility.json` is `2026-03-08T03:53:36Z`, and `catalog/registries.json` is `2026-03-08T04:33:16Z`.
- Why this matters:
  - Consumers cannot treat `catalog/`, `active.json`, `compatibility.json`, and `registries.json` as one release-consistent snapshot.
  - A downstream tool may read a mixed bundle assembled across different runs.
- v9 action:
  - Introduce a bundle revision / snapshot ID shared by all generated outputs.
  - Either rewrite all catalog files atomically together or emit a top-level manifest that binds them.

## Dependency and runtime drift concerns

### 8. Runtime dependencies are implicit and unpinned

- Severity: Medium
- Evidence:
  - Repository automation depends on system `bash`, `python3`, `git`, `ssh-keygen`, and optionally `gh`, but there is no pinned dev environment, no bootstrap script, and no lockfile.
  - `.github/workflows/validate.yml:14` pins CI to Python `3.11`, while local scripts use generic `python3` shebangs and command invocations.
  - There are no repository-level automated tests beyond static validation; only template smoke docs exist under `templates/*/tests`.
- Why this matters:
  - The same commands can behave differently across operator laptops, CI, and future remote registries.
  - As signing and multi-registry logic grows, environment drift becomes a bigger source of false negatives and hard-to-reproduce failures.
- v9 action:
  - Add a reproducible toolchain definition (for example, devcontainer, nix, uv/venv bootstrap, or a documented minimum tool matrix).
  - Add CI jobs that exercise the release and sync scripts in a controlled environment.

### 9. Skill dependency resolution is still prone to drift once real cross-skill graphs appear

- Severity: Medium
- Evidence:
  - `policy/promotion-policy.json:18` to `policy/promotion-policy.json:24` allows name-only dependency refs and auto-installs dependencies by default.
  - `scripts/install-skill.sh:92` to `scripts/install-skill.sh:120` recursively installs dependencies and carries forward the resolved registry, but unpinned refs still resolve against the current registry view.
  - `scripts/check-registry-integrity.py:60` to `scripts/check-registry-integrity.py:73` only requires active dependencies to resolve somewhere in active or archived, not to an immutable exact source.
- Why this matters:
  - As soon as the repo has real active skills, a dependency specified as `name` rather than `name@version` can drift to a different active version or different higher-priority registry over time.
  - Current install manifests help after installation, but author-time metadata is still loose.
- v9 action:
  - Require exact version refs for active-skill dependencies.
  - Record the resolved registry and commit for each dependency edge.
  - Add cycle, downgrade, and mixed-registry integration tests.

## Process blockers and fragile areas

### 10. The riskiest workflows are not covered by end-to-end automation

- Severity: High
- Evidence:
  - `.github/workflows/validate.yml:15` runs only `scripts/check-all.sh`.
  - There are no repo-level test suites for `scripts/install-skill.sh`, `scripts/sync-registry-source.sh`, `scripts/promote-skill.sh`, `scripts/release-skill.sh`, or provenance verification.
  - `catalog/catalog.json` and `catalog/active.json` both show zero skills today, so release/promotion behavior is largely unexercised against live registry content.
- Why this matters:
  - The codebase already has sophisticated lifecycle tooling, but the most failure-prone flows still depend on manual confidence.
  - v9 planning should assume hidden defects remain in multi-registry, rollback, and release paths until they are exercised end-to-end.
- v9 action:
  - Create fixture skills and a fixture secondary registry.
  - Add CI scenarios for promote → build catalog → install → sync → release → verify provenance.

### 11. Some scripts are non-atomic and can leave the repo in an in-between state on failure

- Severity: Medium
- Evidence:
  - `scripts/promote-skill.sh:53` to `scripts/promote-skill.sh:67` deletes/replaces active content and only rebuilds catalog afterward.
  - `scripts/install-skill.sh:133` to `scripts/install-skill.sh:141` and `scripts/sync-skill.sh:87` to `scripts/sync-skill.sh:89` remove and copy directories directly rather than swapping atomically.
- Why this matters:
  - A failed catalog build, interrupted copy, or partial filesystem error can leave registry or install targets inconsistent.
- v9 action:
  - Use temp directories plus atomic rename where possible.
  - Add rollback or repair steps for promotion and sync failures.

## Immediate planning recommendation for v9

If v9 can only tackle a few items, the recommended order is:

1. Make registry sync safe (`self` must never hard-reset the working repo).
2. Enforce immutable source resolution (pinned commits/tags, trust policy enforcement).
3. Make review quorum authoritative (CODEOWNERS / protected branch / computed approval state).
4. Make release output atomic and attestable (clean tree check, signed tag, snapshot ID, default provenance verification).
5. Add end-to-end fixture tests before expanding multi-registry rollout.

Until those are addressed, the biggest blocker is that the repository already exposes multi-registry, review, and provenance features, but the most security-sensitive and correctness-sensitive paths are still optional, mutable, or unsafe by default.
