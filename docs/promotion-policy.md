# Promotion Policy

Version 6 introduces a machine-readable promotion policy file:

- `policy/promotion-policy.json`

Version 11-01 also allows reusable defaults to come from `policy/policy-packs.json` and `policy/packs/*.json`, but `policy/promotion-policy.json` still remains the final repository-local override layer.

## Why this exists

Earlier versions encoded promotion expectations partly in docs and partly in shell scripts. The policy file makes those rules explicit and reviewable.

## Current policy checks

For `active` skills, the policy currently requires:

- computed `review_state` to resolve to `approved`
- `CHANGELOG.md` present
- smoke test present
- owner present
- `reviews.json` present
- minimum counted reviewer approvals
- required reviewer-group coverage

## Review groups and quorum

Reviewer governance lives under `reviews` in `policy/promotion-policy.json`.

If policy packs are enabled, the effective promotion policy is:

1. ordered pack values from `policy/policy-packs.json`
2. merged `promotion_policy` domains from `policy/packs/*.json`
3. final repository-local overrides from `policy/promotion-policy.json`

- `groups` defines the configured reviewer identities and their group membership
- `quorum.defaults` sets the baseline quorum
- `quorum.stage_overrides` adjusts quorum by lifecycle stage
- `quorum.risk_overrides` adjusts quorum by risk level
- `quorum.stage_risk_overrides` can refine a specific stage+risk combination

The effective review result always comes from the latest distinct reviewer decisions after those rules are applied.

Review decisions can come from two additive sources:

- `reviews.json` for repo-local requests and approvals
- `review-evidence.json` for normalized imported platform-native review evidence

Imported evidence must stay file-backed and auditable. Each entry carries `source`, `source_kind`, `source_ref`, `reviewer`, `decision`, `at`, and optional `url` or `note`, and those fields remain visible in JSON outputs instead of collapsing into anonymous approval counts.

That merged evidence set is what powers:

- `scripts/review-status.py --json`
- `scripts/check-promotion-policy.py --json`
- `scripts/check-release-state.py --json`
- `scripts/build-catalog.sh`

If imported evidence is malformed, or if the same reviewer is duplicated inside `review-evidence.json`, validation fails explicitly.

## Reviewer guidance

Promotion policy still defines the rules; reviewer recommendation tooling only reads them.

- `python3 scripts/recommend-reviewers.py <skill> --as-active --json` evaluates the effective quorum rule for the target stage
- recommendations are grouped by required reviewer group, with missing groups prioritized first
- exclusions include policy-driven reasons such as owner conflicts or reviewers whose current latest decision is already counted
- when no eligible reviewer exists for a required group, the tooling emits escalation guidance instead of silently guessing

This keeps reviewer rotation deterministic and advisory without adding a scheduler or external state.

Additional checks for `high` risk active skills:

- minimum maintainer count
- explicit `requires` block

## Enforcement

The policy is enforced by:

- `scripts/check-policy-packs.py`
- `scripts/check-promotion-policy.py`
- `scripts/check-all.sh`

and is intended to be called before promotion as the registry evolves further.
