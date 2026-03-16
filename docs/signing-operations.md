# Signing Operations

This guide covers the steady-state operator workflow after the first trusted signer and first stable release already exist.

## Current repository state

- `config/allowed_signers` includes a committed `lvxiaoer` trusted signer entry.
- `operate-infinitas-skill` already has a signed pushed stable tag plus verified provenance.
- `scripts/report-signing-readiness.py` is the quickest way to confirm that the repo still matches those expectations.

## Daily readiness check

Use the repository-level report before a release rehearsal, key change, or provenance verification pass:

```bash
python3 scripts/report-signing-readiness.py --skill operate-infinitas-skill --json
```

That report summarizes:

- committed trusted signer identities
- whether the locally configured SSH signing key matches a trusted signer
- per-skill release tag status
- provenance verification status
- namespace-policy signer and releaser authorization

For a deeper, single-skill diagnostic, follow up with:

```bash
python3 scripts/doctor-signing.py operate-infinitas-skill --provenance catalog/provenance/operate-infinitas-skill-0.1.1.json
```

## Add another signer

When a second maintainer or release bot needs signing authority:

```bash
python3 scripts/bootstrap-signing.py add-allowed-signer \
  --identity release-bot \
  --key ~/.ssh/release-bot-signing
python3 scripts/bootstrap-signing.py authorize-publisher \
  --publisher lvxiaoer \
  --signer release-bot \
  --releaser release-bot
git add config/allowed_signers policy/namespace-policy.json
git commit -m "chore: authorize additional release signer"
```

Then rerun the readiness report to confirm the new signer is visible and trusted.

## Replace an existing signing key

If a signer rotates keys:

1. Generate or recover the replacement key locally.
2. Re-run `bootstrap-signing.py add-allowed-signer` with the same signer identity and new key path.
3. Update local git signing config with `bootstrap-signing.py configure-git --key ...`.
4. Commit the updated `config/allowed_signers`.
5. Re-run `report-signing-readiness.py` and `doctor-signing.py` before tagging again.

Using the same identity keeps namespace policy stable while rotating only the trusted public key material.

## Verify provenance without cutting a new release

When you need to re-check existing release evidence:

```bash
python3 scripts/report-signing-readiness.py --skill operate-infinitas-skill --json
python3 scripts/verify-attestation.py catalog/provenance/operate-infinitas-skill-0.1.1.json
python3 scripts/doctor-signing.py operate-infinitas-skill --provenance catalog/provenance/operate-infinitas-skill-0.1.1.json
```

The report confirms the high-level state, the attestation verifier checks the provenance bundle, and doctor explains any mismatch between signer policy, local git config, and release metadata.
