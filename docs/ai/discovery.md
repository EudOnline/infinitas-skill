# Discovery and Install Semantics

Private-first discovery is audience-aware.

There are two complementary surfaces:

- `/registry/discovery-index.json`: listed releases that may be searched or recommended
- `/registry/ai-index.json`: installable releases visible to the current audience

The API mirrors the same split:

- `/api/v1/catalog/{public|me|grant}` for list views
- `/api/v1/search/{public|me|grant}` for search
- `/api/v1/install/{public|me|grant}/{skill_ref}` for exact install resolution

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
