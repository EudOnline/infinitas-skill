# Release, Tag, and Attestation Strategy

This repository tracks skill evolution inside git, but stable release artifacts now resolve against immutable git tags instead of best-effort local branch state.

## Versioning

Use semantic versioning for every skill:

- `major`: incompatible workflow or contract change
- `minor`: meaningful capability expansion, new references, new scripts, or changed behavior
- `patch`: wording cleanup, metadata fixes, small corrections

## Changelog policy

Every skill under `skills/` should keep a `CHANGELOG.md`.

Recommended format:

```md
# Changelog

## 0.2.0 - 2026-03-08
- Added manifest-aware install flow.
- Added lineage diff helper.
```

## Tag naming

Stable release tags use a per-skill naming convention:

- `skill/<name>/v<version>`

Examples:

- `skill/repo-audit/v0.3.0`
- `skill/feishu-doc/v1.0.0`

This avoids collisions across many skills living in one repository.

## Stable release invariants

Stable release tooling enforces all of the following before it will write release notes, provenance, or GitHub releases:

1. the repository worktree is clean
2. the current branch tracks an upstream and is fully synchronized with it
3. the expected tag `skill/<name>/v<version>` exists locally, points at `HEAD`, is signed, and verifies against repo-managed signers
4. that same tag is already pushed to the tracked remote
5. the skill's publisher / namespace claim is valid under `policy/namespace-policy.json`

If any of those invariants fail, `scripts/release-skill.sh` and `scripts/check-release-state.py` exit with actionable errors.

## Delegated audit metadata

11-05 keeps the audit surface on the existing release-state and provenance path instead of adding a separate export product.

- `python3 scripts/check-release-state.py <name> --json` now exports richer review audit context, including `effective_review_state`, quorum counters, `latest_decisions`, `ignored_decisions`, and `configured_groups`.
- That same JSON now records delegated release authority via `release.delegated_teams` and mirrors applied break-glass overrides into `release.exception_usage` while preserving the existing top-level `exception_usage`.
- Generated provenance carries the same stable audit metadata so later reviewers can reconstruct delegated approvals plus release exceptions without depending on debug-only `policy_trace` output.

## Audit and inventory export artifacts

11-07 turns those previously internal stable artifacts into two explicit integration surfaces:

- `catalog/audit-export.json`
- `catalog/inventory-export.json`

The split is intentional:

- `audit-export.json` is provenance-derived and should be treated as immutable release evidence for portal, compliance, or reporting consumers.
- `inventory-export.json` is catalog-derived and should be treated as the current registry and skill inventory view, including federation visibility and release/installability summary.

Installed-integrity capability is additive on the immutable release surfaces:

- `catalog/distributions.json` includes `installed_integrity_capability` and optional `installed_integrity_reason` per released version
- `catalog/catalog.json` mirrors the same signal in `verified_distribution.installed_integrity_capability`
- `catalog/inventory-export.json` mirrors that immutable release capability as `release_installed_integrity_capability`

`audit-export.json` remains release-scoped provenance evidence. It must not absorb local installed-runtime state from one machine or target directory.

Neither export includes raw `policy_trace`. Debug traces remain operator-oriented and live on the existing CLI surfaces.

When release evidence, inventory exports, or federation state appear to disagree, use [docs/federation-operations.md](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules/docs/federation-operations.md) as the recovery guide. The short version is: validate policy first, then rebuild catalog artifacts, then verify provenance and distribution manifests before trusting a released artifact again.

## Stable attestation policy

Phase 5 adds a second enforcement layer on top of the signed-tag baseline.

- `scripts/release-skill.sh <name> --write-provenance` now writes a release attestation payload that includes the immutable source snapshot, resolved registry context, dependency resolution plan, author, reviewer, releaser, signer identities, delegated review context, delegated release authority, applied release exceptions, and deterministic bundle metadata under `distribution`.
- That payload is SSH-signed and verified against `config/allowed_signers` before the release helper accepts it as valid.
- When the v9 attestation policy is enabled, commands that write release artifacts or distribution output must also use `--write-provenance`; otherwise the helper rejects them with an actionable error.
- Use `scripts/verify-attestation.py <attestation.json>` to verify a generated attestation bundle directly. `--json` now surfaces a compact `distribution` summary, including `file_manifest_count` and the signed normalized `build` metadata.

The `distribution` section now carries more than just top-level bundle identity:

- `bundle` still records the released archive path, digest, size, root directory, and file count
- `file_manifest` records the per-file released inventory with relative paths plus SHA-256 digests
- `build` records normalized archive settings and a compact builder summary so later verification can reason about reproducibility instead of only top-level bundle bytes

Downstream audit surfaces now preserve the same additive reproducibility evidence:

- `scripts/check-release-state.py <name> --json` includes `release.reproducibility`
- `catalog/catalog.json` mirrors `verified_distribution.file_manifest_count` and `verified_distribution.build_archive_format`
- `scripts/verify-distribution-manifest.py` validates both the manifest-vs-attestation contract and the actual archived bundle contents against the signed file inventory

The signing policy now also carries an optional `attestation.transparency_log` contract with `disabled`, `advisory`, and `required` modes. That lets the repository stage external transparency publication as an additive second trust layer without replacing the existing offline SSH and CI verification paths.

When that block is enabled, `scripts/release-skill.sh --write-provenance` will:

- publish the signed attestation digest to the configured endpoint
- persist the returned proof record in `catalog/provenance/<skill>-<version>.transparency.json`
- expose the normalized proof summary through `verify-attestation --json`, `check-release-state --json`, and catalog exports

In `required` mode the helper aborts the release and deletes staged provenance output if transparency publication fails, the endpoint is missing, or the returned proof does not match the attestation digest.

## Bootstrap the signer allowlist

This repository intentionally keeps the stable release trust root in-versioned files.

For a fresh repository's first stable release tag, populate `config/allowed_signers` with one or more trusted signer identities:

```text
release-bot ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...
```

Then commit and push that change before creating the tag. A comment-only or empty `config/allowed_signers` file blocks stable releases by design.

This repository already has a committed `lvxiaoer` signer entry, so the usual operator path is to confirm current state with:

```bash
python3 scripts/report-signing-readiness.py --skill operate-infinitas-skill --json
```

For the steady-state playbook after bootstrap, see `docs/signing-operations.md`.

Committed signer entries are expected to contain only public signer identities and public keys. Never commit private SSH keys.

## Git SSH signing setup

Stable tags default to SSH signing. A typical local setup is:

```bash
git config gpg.format ssh
git config user.signingkey ~/.ssh/id_ed25519
```

You can also point the release helper at a key just for one command by exporting:

```bash
export INFINITAS_SKILL_GIT_SIGNING_KEY=~/.ssh/id_ed25519
```

## Promotion guidance

Typical flow:

1. Work in `skills/incubating/<name>`
2. Update `_meta.json.version`
3. Add or update `CHANGELOG.md`
4. Run `scripts/check-all.sh`
5. Ensure `scripts/review-status.py <name> --as-active --require-pass` succeeds
6. Promote to `skills/active/`
7. Populate or review `config/allowed_signers` if this is the first signed release for the signer set
8. Create and push the signed release tag
9. Generate release notes, provenance, or GitHub release from that pushed tag

## Helpful commands

```bash
# bump patch version and seed changelog entry
scripts/bump-skill-version.sh repo-audit patch --note "Refined repo scoring rubric"

# inspect lineage against a declared ancestor
scripts/lineage-diff.sh repo-audit-plus
```

## Tag helper

Use the helper to print the expected tag, create it locally, or push it after local verification:

```bash
# print the recommended tag
scripts/release-skill-tag.sh repo-audit

# create and locally verify the signed tag
scripts/release-skill-tag.sh repo-audit --create

# create, push, and verify the signed tag against the tracked remote
scripts/release-skill-tag.sh repo-audit --create --push
```

`--unsigned` still exists for local experiments, but stable release tooling rejects unsigned tags.

## First trusted signer bootstrap

Fresh repositories may start with comments only in `config/allowed_signers`, so the first stable tag is intentionally blocked until maintainers commit a trusted signer identity.

Use the bootstrap helper to:

```bash
python3 scripts/bootstrap-signing.py init-key --identity lvxiaoer --output ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py add-allowed-signer --identity lvxiaoer --key ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py configure-git --key ~/.ssh/infinitas-skill-release-signing
python3 scripts/bootstrap-signing.py authorize-publisher --publisher lvxiaoer --signer lvxiaoer --releaser lvxiaoer
python3 scripts/doctor-signing.py repo-audit
```

For a full walkthrough, see `docs/signing-bootstrap.md`.

## Release helper

Use the higher-level helper to preview notes, verify release readiness, and then emit immutable release artifacts:

```bash
# preview release notes without enforcing stable release invariants
scripts/release-skill.sh repo-audit --preview

# create, push, and verify the default signed stable tag
scripts/release-skill.sh repo-audit --push-tag

# verify the repo is fully release-ready
scripts/check-release-state.py repo-audit

# inspect local provenance output, including reproducibility summary
scripts/check-release-state.py repo-audit --mode local-tag --json

# write release notes and provenance from the pushed signed tag
scripts/release-skill.sh repo-audit --notes-out /tmp/repo-audit-release.md --write-provenance --releaser lvxiaoer

# verify the resulting attestation bundle
scripts/verify-attestation.py catalog/provenance/repo-audit-0.3.0.json
python3 scripts/doctor-signing.py repo-audit --provenance catalog/provenance/repo-audit-0.3.0.json

# inspect transparency proof state when configured
python3 scripts/verify-attestation.py catalog/provenance/repo-audit-0.3.0.json --json
```

If you also pass `--github-release`, the helper will call `gh release create` with notes that include the immutable source snapshot.

Under the v9 policy, `--github-release` and `--notes-out` must be paired with `--write-provenance` so the emitted artifact is backed by a verified attestation.

After writing provenance, doctor may warn that the worktree is dirty until those generated release artifacts are committed or cleaned. That warning is about the next release ceremony, not the attestation you just verified.

`check-release-state.py --mode local-tag` follows the same model: it still reports the dirty worktree as a warning, but it does not fail solely because repo-managed provenance artifacts were written for a local signed-tag release.

If you omit `--releaser`, release tooling records `INFINITAS_SKILL_RELEASER` when set and otherwise falls back to `git config user.name` / `user.email`.

## Provenance signing

Once the signed git tag is already verified, the SSH release attestation is the authoritative verification path. You can still add optional sidecar signatures afterward.

If `INFINITAS_SKILL_SIGNING_KEY` is set, release tooling can sign provenance bundles via:

```bash
scripts/release-skill.sh repo-audit --write-provenance --sign-provenance
```

That produces a legacy HMAC sidecar (`.sig.json`) and verifies it immediately. It does not replace the required SSH attestation.

## SSH provenance signing

In addition to the automatic SSH attestation flow in `scripts/release-skill.sh --write-provenance`, you can sign a payload manually with SSH keys:

```bash
scripts/release-skill.sh repo-audit --write-provenance --ssh-sign-provenance --ssh-key ~/.ssh/id_ed25519
```

To verify, either use the high-level attestation verifier or the shell wrapper:

```bash
scripts/verify-attestation.py catalog/provenance/repo-audit-0.3.0.json
scripts/release-skill.sh repo-audit --write-provenance --ssh-verify-provenance --signer registry-signer
```
