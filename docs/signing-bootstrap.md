# Signing Bootstrap and First Stable Release

Fresh repositories typically begin with comment-only guidance in `config/allowed_signers` until maintainers commit the first trusted signer identities.

This repository is already bootstrapped with a committed `lvxiaoer` signer entry plus a verified stable release for `operate-infinitas-skill`.

This guide covers the bootstrap flow for that first trusted stable release.

For the current repository state, check the live status first:

```bash
python3 scripts/report-signing-readiness.py --skill my-skill --json
```

If you need the steady-state operator playbook after bootstrap is already complete, see `docs/signing-operations.md`.

Signing defaults may now be seeded from ordered packs declared in `policy/policy-packs.json`, but `config/signing.json` still wins last as the repository-local override layer for the effective `signing` domain.

## 1. Generate or reuse a signing key

Create a dedicated SSH signing key:

```bash
python3 scripts/bootstrap-signing.py init-key \
  --identity lvxiaoer \
  --output ~/.ssh/infinitas-skill-release-signing
```

If you already have an SSH signing key, skip straight to the next step and pass that existing key path instead.

## 2. Trust the signer in-repo

Add or update the committed allowed signer entry:

```bash
python3 scripts/bootstrap-signing.py add-allowed-signer \
  --identity lvxiaoer \
  --key ~/.ssh/infinitas-skill-release-signing
```

That updates `config/allowed_signers` with the public key only. Never commit the private key.

## 3. Point git at the signing key

Configure the local repository to use SSH tag signing:

```bash
python3 scripts/bootstrap-signing.py configure-git \
  --key ~/.ssh/infinitas-skill-release-signing
```

This sets:

- `git config gpg.format ssh`
- `git config user.signingkey ~/.ssh/infinitas-skill-release-signing`

You can also keep using `INFINITAS_SKILL_GIT_SIGNING_KEY`, but local git config is usually easier for operators.

## 4. Wire signer and releaser identities into publisher policy

If the skill uses a publisher namespace, authorize the identities that will sign and release it:

```bash
python3 scripts/bootstrap-signing.py authorize-publisher \
  --publisher lvxiaoer \
  --signer lvxiaoer \
  --releaser lvxiaoer
```

This updates `policy/namespace-policy.json` without changing any release gates.

## 5. Commit the trust-root changes

Before the first stable tag, commit and push the repo-managed trust changes:

```bash
git add config/allowed_signers policy/namespace-policy.json
git commit -m "chore: bootstrap trusted release signer"
git push
```

The stable release flow requires a clean, synchronized worktree, so this commit needs to land before tagging.

If the repository uses policy packs, keep any long-lived shared defaults in `policy/packs/*.json` and reserve `config/signing.json` for repository-specific overrides that should beat pack defaults.

## 6. Run the signing doctor

Check signer readiness before the first stable tag:

```bash
python3 scripts/doctor-signing.py my-skill
```

Use `--json` for machine-readable output.

Doctor reports:

- committed trusted signers
- effective SSH signing key configuration
- whether the configured key matches `config/allowed_signers`
- namespace-policy signer/releaser authorization warnings
- release preflight blockers such as dirty worktrees or upstream drift
- whether the signed tag or attestation bundle already exists

Resolve every `FAIL` item before creating the first stable tag.

For repository-level status beyond a single skill, use:

```bash
python3 scripts/report-signing-readiness.py --skill my-skill --json
```

## 7. Rehearse the first stable release

Once doctor is green, the stable release ceremony is:

```bash
scripts/release-skill.sh my-skill --push-tag
scripts/release-skill.sh my-skill \
  --notes-out /tmp/my-skill-release.md \
  --write-provenance \
  --releaser lvxiaoer
python3 scripts/doctor-signing.py \
  my-skill \
  --provenance catalog/provenance/my-skill-1.2.3.json
```

The first command creates and pushes the signed tag.

The second command writes release notes plus the SSH-verified release attestation.

The final doctor run confirms that the current attestation verifies and tells you if generated release artifacts now need to be committed before the next release.

## 8. Existing-key shortcut

If you already have a signer key, the minimal bootstrap is:

```bash
python3 scripts/bootstrap-signing.py add-allowed-signer --identity lvxiaoer --key ~/.ssh/id_ed25519
python3 scripts/bootstrap-signing.py configure-git --key ~/.ssh/id_ed25519
python3 scripts/bootstrap-signing.py authorize-publisher --publisher lvxiaoer --signer lvxiaoer --releaser lvxiaoer
python3 scripts/doctor-signing.py my-skill
```

That is enough to wire an existing signer into repository policy without generating new key material.
