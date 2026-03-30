---
audience: operators and release maintainers
owner: repository maintainers
source_of_truth: signing operations runbook
last_reviewed: 2026-03-30
status: maintained
---

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

## Transparency log policy

The signing policy now reserves an additive transparency-log block under `config/signing.json`:

```json
"attestation": {
  "transparency_log": {
    "mode": "disabled",
    "endpoint": null,
    "timeout_seconds": 5
  }
}
```

The modes mean:

- `disabled`: do not attempt external transparency publication
- `advisory`: attempt publication when a caller asks for it, but do not fail the release if the endpoint is unavailable
- `required`: treat missing endpoint, malformed responses, or proof mismatches as release-blocking errors for callers that enforce transparency publication

The returned log-entry contract is normalized into a stable JSON shape with `entry_id`, `log_index`, `integrated_time`, `attestation_sha256`, and `proof` fields so later release tooling can persist and audit the same proof record.

When `scripts/release-skill.sh --write-provenance` runs with transparency publication enabled, it writes that normalized proof to:

```text
catalog/provenance/<skill>-<version>.transparency.json
```

Operationally:

- `advisory` mode logs a warning and continues if the endpoint is unavailable or returns a bad proof
- `required` mode fails the release before distribution artifacts are finalized, so no half-trusted release bundle is left behind
- `python3 scripts/verify-attestation.py <attestation.json> --json` is the fastest way to confirm whether the stored transparency proof still matches the attestation digest
