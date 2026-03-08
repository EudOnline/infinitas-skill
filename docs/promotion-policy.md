# Promotion Policy

Version 6 introduces a machine-readable promotion policy file:

- `policy/promotion-policy.json`

## Why this exists

Earlier versions encoded promotion expectations partly in docs and partly in shell scripts. The policy file makes those rules explicit and reviewable.

## Current policy checks

For `active` skills, the policy currently requires:

- approved `review_state`
- `CHANGELOG.md` present
- smoke test present
- owner present
- `reviews.json` present
- minimum distinct reviewer approvals

Additional checks for `high` risk active skills:

- minimum maintainer count
- explicit `requires` block

## Enforcement

The policy is enforced by:

- `scripts/check-promotion-policy.py`
- `scripts/check-all.sh`

and is intended to be called before promotion as the registry evolves further.
