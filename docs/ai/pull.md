---
audience: contributors, integrators, automation authors
owner: repository maintainers
source_of_truth: legacy ai protocol annex
last_reviewed: 2026-04-21
status: legacy
---

# Pull and Download

Hosted private-first pulls are release-artifact downloads, not mutable source checkouts.

## Preferred sequence

1. Resolve discoverability through `/registry/discovery-index.json` or `/api/v1/search/*`
2. Resolve an exact install target through `/api/v1/install/{public|me|grant}/{skill_ref}`
3. Download the returned `manifest`, `bundle`, `provenance`, and `signature`
4. Treat those files as immutable release artifacts

## Important constraints

- do not read `skills/active/` or `skills/incubating/` as install inputs
- do not depend on legacy review or submission state
- do not assume a token expands visibility beyond its audience scope
- do not guess artifact paths; use the paths returned by install resolution

## Verification requirements

Install-resolution responses may declare `required_formats` so callers know which release artifacts must be fetched and verified before installation is trusted.

When provenance or manifest verification is required:

- use `python3 scripts/verify-distribution-manifest.py ...` to confirm the downloaded distribution manifest still matches the referenced artifacts
- verify CI attestation when the release publishes a CI-native provenance bundle alongside the SSH attestation record
- treat missing required artifacts as a blocking install error rather than silently falling back to partial verification

## Registry aliases

The server also serves the same artifacts under `/registry/*`, including legacy catalog aliases:

- `/registry/skills/{publisher}/{skill}/{version}/manifest.json`
- `/registry/skills/{publisher}/{skill}/{version}/skill.tar.gz`
- `/registry/provenance/{publisher}--{skill}-{version}.json`
- `/registry/provenance/{publisher}--{skill}-{version}.json.ssig`
- `/registry/catalog/distributions/...`
- `/registry/catalog/provenance/...`

Those aliases are backed by the same private-first release graph and access checks.

## Installed integrity follow-up

Pull and install flows end with local verification, not just artifact download.

- run `python3 scripts/report-installed-integrity.py <target-local> --json` after install when you need the current trust state of that target-local copy
- `.infinitas-skill-installed-integrity.json` records the installed integrity snapshot beside the target-local runtime
- `catalog/audit-export.json` remains the repository-side audit export for released artifacts, not a substitute for verifying the target-local install
