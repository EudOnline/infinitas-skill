# Promotion Policy

Version 6 introduces a machine-readable promotion policy file:

- `policy/promotion-policy.json`

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

- `groups` defines the configured reviewer identities and their group membership
- `quorum.defaults` sets the baseline quorum
- `quorum.stage_overrides` adjusts quorum by lifecycle stage
- `quorum.risk_overrides` adjusts quorum by risk level
- `quorum.stage_risk_overrides` can refine a specific stage+risk combination

The effective review result always comes from the latest distinct reviewer decisions after those rules are applied.

Additional checks for `high` risk active skills:

- minimum maintainer count
- explicit `requires` block

## Enforcement

The policy is enforced by:

- `scripts/check-promotion-policy.py`
- `scripts/check-all.sh`

and is intended to be called before promotion as the registry evolves further.
