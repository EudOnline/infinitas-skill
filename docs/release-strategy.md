# Release and Tag Strategy

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

If any of those invariants fail, `scripts/release-skill.sh` and `scripts/check-release-state.py` exit with actionable errors.

## Bootstrap the signer allowlist

This repository intentionally keeps the stable release trust root in-versioned files.

Before the first stable release tag can be verified, populate `config/allowed_signers` with one or more trusted signer identities:

```text
release-bot ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...
```

Then commit and push that change before creating the tag. A comment-only or empty `config/allowed_signers` file blocks stable releases by design.

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

## Release helper

Use the higher-level helper to preview notes, verify release readiness, and then emit immutable release artifacts:

```bash
# preview release notes without enforcing stable release invariants
scripts/release-skill.sh repo-audit --preview

# create, push, and verify the default signed stable tag
scripts/release-skill.sh repo-audit --push-tag

# verify the repo is fully release-ready
scripts/check-release-state.py repo-audit

# write release notes and provenance from the pushed signed tag
scripts/release-skill.sh repo-audit --notes-out /tmp/repo-audit-release.md --write-provenance
```

If you also pass `--github-release`, the helper will call `gh release create` with notes that include the immutable source snapshot.

## Provenance signing

Once the signed git tag is already verified, you can optionally add provenance sidecar signatures.

If `INFINITAS_SKILL_SIGNING_KEY` is set, release tooling can sign provenance bundles via:

```bash
scripts/release-skill.sh repo-audit --write-provenance --sign-provenance
```

That produces a sidecar signature file (`.sig.json`) and verifies it immediately.

## SSH provenance signing

In addition to HMAC signing, provenance can be signed with SSH keys:

```bash
scripts/release-skill.sh repo-audit --write-provenance --ssh-sign-provenance --ssh-key ~/.ssh/id_ed25519
```

To verify, provide the signer identity and an allowed signers file:

```bash
scripts/release-skill.sh repo-audit --write-provenance --ssh-verify-provenance --signer registry-signer
```
