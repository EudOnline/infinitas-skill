---
audience: contributors, integrators, release maintainers
owner: repository maintainers
source_of_truth: maintained release trust and attestation reference
last_reviewed: 2026-07-14
status: maintained
---

# Release Attestation

Stable releases can require one of three release trust modes through `config/signing.json` under `attestation.policy.release_trust_mode`:

- `ssh`: require the repository-managed SSH attestation
- `ci`: require CI attestation as the release trust signal
- `both`: require SSH and CI attestation together

This is the maintained reference for CI-native attestation and CI attestation verification.

## Offline Verification

Offline verification uses downloaded release artifacts only:

```bash
uv run infinitas release verify-attestation catalog/provenance/my-skill-1.2.3.json --json
uv run infinitas release verify-ci-attestation catalog/provenance/my-skill-1.2.3.ci.json --json
```

What this checks:

- SSH provenance signature and allowed signer policy
- CI attestation repository, workflow, ref, and commit consistency
- distribution manifest integrity and artifact digests
- manifest `required_formats` so callers can enforce `ssh`, `ci`, or `both`

## Online Verification

Online verification is optional and adds operator confidence:

- compare CI attestation `repository`, `workflow`, `run_id`, and `url` with the real GitHub Actions run
- confirm the workflow ran against the expected immutable ref
- confirm the live run metadata still matches the signed source snapshot

The repository workflow scaffold lives at `.github/workflows/release-attestation.yml`.

Create the current distribution manifest with `infinitas release generate-distribution-manifest`; verification then follows the manifest references and signed attestation evidence.

## How To Read The Policy

Use `release_trust_mode` this way:

- `ssh` when repository-managed signing is the only required trust signal
- `ci` when CI attestation is required
- `both` when both SSH and CI-native attestation must verify before the release is trusted

If a manifest or install-resolution response exposes `required_formats`, treat missing required artifacts as a blocking error instead of falling back to partial verification.

## Where This Fits

- [Release checklist](../ops/release-checklist.md) is the operational go/no-go list.
- [Distribution manifests](distribution-manifests.md) defines the immutable artifact contract those checks operate on.
