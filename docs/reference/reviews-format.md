---
audience: contributors, reviewers
owner: repository maintainers
source_of_truth: reviews.json format
last_reviewed: 2026-04-22
status: maintained
---

# Reviews Format

Schema and semantics for the per-skill `reviews.json` file that tracks review requests and decisions in the local registry.

## File location

Each skill directory contains a `reviews.json` file:

```text
skills/active/<skill-name>/reviews.json
```

## Top-level structure

| Field | Type | Description |
|---|---|---|
| `version` | `integer` | Schema version. Always `1`. |
| `requests` | `array` | Ordered log of review requests. |
| `entries` | `array` | Ordered log of review decisions. |

## `requests[]` objects

Each element records one review request.

| Field | Type | Required | Description |
|---|---|---|---|
| `requested_at` | `string` | yes | ISO 8601 UTC timestamp (e.g. `"2026-03-12T12:14:27Z"`) |
| `note` | `string\|null` | no | Optional context for why the review was requested. `null` when omitted. |

## `entries[]` objects

Each element records one review decision.

| Field | Type | Required | Description |
|---|---|---|---|
| `reviewer` | `string` | yes | Handle of the reviewer. Must be a configured reviewer in promotion policy. |
| `decision` | `string` | yes | One of `"approved"` or `"rejected"`. |
| `note` | `string\|null` | no | Optional reviewer note. `null` when omitted. |
| `at` | `string` | yes | ISO 8601 UTC timestamp (e.g. `"2026-03-12T12:14:51Z"`) |

## Example

```json
{
  "version": 1,
  "requests": [
    {
      "requested_at": "2026-03-12T12:14:27Z",
      "note": "Release candidate for v0.2.0"
    }
  ],
  "entries": [
    {
      "reviewer": "lvxiaoer",
      "decision": "approved",
      "note": "Changelog and smoke tests verified",
      "at": "2026-03-12T12:14:51Z"
    }
  ]
}
```

## Policy evaluation

Review state is computed by evaluating `entries[]` against the promotion policy:

Note: the hosted registry CLI uses `"approve"/"reject"` (present tense) for `reviews decide --decision`, while the local `reviews.json` entries use `"approved"/"rejected"` (past tense). These are two separate systems with different decision vocabularies.

1. Each entry's `reviewer` must belong to a configured reviewer group in `policy/promotion-policy.json`
2. Quorum requires the configured minimum number of approvals from the relevant group
3. `rejected` decisions do not count toward quorum but are recorded for audit

The policy engine also merges entries from `review-evidence.json` (platform-native approval evidence) alongside local `reviews.json` entries. Merged entries carry additional provenance fields:

| Field | Default for local entries |
|---|---|
| `source` | `"reviews.json"` |
| `source_kind` | `"repo-review"` |
| `source_ref` | `"reviews.json"` |
| `url` | `null` |

## CLI operations

```bash
# Recommend reviewers for a skill (does not modify reviews.json)
uv run infinitas policy recommend-reviewers <skill> --as-active --json

# Check review status and quorum
uv run infinitas policy review-status <skill> --as-active --json
```

Review requests and decisions can be added by editing `reviews.json` directly, or by calling `request_review()` and `record_review_decision()` from `src/infinitas_skill/policy/reviews.py`. No CLI command currently invokes these functions directly.

## Schema file

Machine-readable JSON Schema: `schemas/reviews.schema.json`

## See also

- [Promotion policy](promotion-policy.md)
- [Metadata schema](metadata-schema.md)
- [Error catalog](error-catalog.md)
