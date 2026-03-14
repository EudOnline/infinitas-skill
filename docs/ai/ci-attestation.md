# CI-native Attestation Verification

## Overview

Stable releases can now enforce one of three trust modes through `config/signing.json`:

- `ssh`: only the repo-managed SSH attestation is required
- `ci`: the CI-generated attestation is required in addition to immutable bundle checks
- `both`: SSH and CI attestations must both verify

The policy lives under `attestation.policy.release_trust_mode`.

## Offline verification

Offline verification uses downloaded release files only:

```bash
python3 scripts/verify-attestation.py catalog/provenance/my-skill-1.2.3.json --json
python3 scripts/verify-ci-attestation.py catalog/provenance/my-skill-1.2.3.ci.json --json
python3 scripts/verify-distribution-manifest.py catalog/distributions/_legacy/my-skill/1.2.3/manifest.json
```

What gets checked offline:

- bundle digest and manifest consistency
- SSH attestation signature and allowed signer policy
- CI payload repository, workflow, ref, and commit consistency
- manifest `required_formats` so consumers can enforce `ssh`, `ci`, or `both`

## Online verification

Online verification is optional and adds operator confidence:

- compare the CI attestation `repository`, `workflow`, `run_id`, and `url` to the real GitHub Actions run
- confirm the workflow ran against the expected tag ref
- confirm the GitHub run metadata still matches the signed source snapshot

The repository workflow scaffold lives at `.github/workflows/release-attestation.yml`.

## Rollout modes

- `ssh`: current default; CI sidecars may exist but are not required
- `ci`: useful when automation is the authoritative build prover
- `both`: strongest mode during rollout because local SSH provenance and CI provenance must agree
