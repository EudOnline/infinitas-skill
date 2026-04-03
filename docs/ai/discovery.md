# Discovery and Install Semantics

Private-first discovery is audience-aware.

There are two complementary surfaces:

- `/registry/discovery-index.json`: listed releases that may be searched or recommended
- `/registry/ai-index.json`: installable releases visible to the current audience

The API mirrors the same split:

- `/api/v1/catalog/{public|me|grant}` for list views
- `/api/v1/search/{public|me|grant}` for search
- `/api/v1/install/{public|me|grant}/{skill_ref}` for exact install resolution

For ranked recommendations on top of those audience-scoped views, use `scripts/recommend-skill.sh` so the caller gets one best-fit result plus comparison signals instead of a raw list.

## Listing rules

- `listing_mode = listed`: release may appear in discovery and catalog views
- `listing_mode = direct_only`: release stays installable by exact reference but is hidden from discovery views

## Audience rules

- `public`: anonymous readers only see active public exposures
- `me`: a user or principal token sees releases allowed by private ownership, explicit grants, and public exposures
- `grant`: a grant token is scoped to the specific grant-linked release only

## Install resolution

`skill_ref` accepts either:

- `publisher/name`
- `publisher/name@version`
- `name`
- `name@version`

Short names must resolve unambiguously within the current audience.

An install response contains:

- `manifest_path`
- `bundle_path`
- `provenance_path`
- `signature_path`
- `bundle_sha256`
- direct download paths and URLs for each artifact

Use the API response as the source of truth for artifact download. Do not infer installability from repository source folders.

## Inspect advisory memory hints

`scripts/inspect-skill.sh` and inspect helpers can surface a memory-assisted advisory block:

- `memory_hints.used`
- `memory_hints.backend`
- `memory_hints.matched_count`
- `memory_hints.status`
- `memory_hints.items[]` (`memory_type`, `memory`, optional `score`)

Example:

```json
{
  "qualified_name": "lvxiaoer/consume-infinitas-skill",
  "trust_state": "verified",
  "memory_hints": {
    "used": true,
    "backend": "memo0",
    "matched_count": 1,
    "advisory_only": true,
    "status": "matched",
    "items": [
      {
        "memory_type": "experience",
        "memory": "OpenClaw installs usually succeed when the release is already materialized.",
        "score": 0.94
      }
    ]
  }
}
```

This memory layer is advisory only:

- trust derivation still comes from manifest, attestation, and signature evidence
- memory hints cannot mark a skill as verified, trusted, or installable
- inspect trust fields remain authoritative even when memory hints are present
- inspect may also return `disabled`, `unavailable`, `no-match`, or `error` in `memory_hints.status` without changing the trust decision

When multiple hints are available, inspect now orders them by advisory quality using the same score inputs as recommendation:

- provider score
- policy confidence
- memory type weighting
- TTL weighting

## Installed integrity follow-up

After a skill is installed into a target-local runtime, verify that concrete copy with `python3 scripts/report-installed-integrity.py <target-local> --json`.

- use `--refresh` when the local report says freshness data needs to be recomputed
- `.infinitas-skill-installed-integrity.json` is the target-local snapshot for that installed copy
- `catalog/audit-export.json` stays the committed release-side audit surface and does not replace target-local verification
