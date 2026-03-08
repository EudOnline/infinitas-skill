# Review Workflow

Version 7 introduces an explicit review workflow for promotion.

## Files

Each skill keeps review evidence in `reviews.json`:

- review requests
- reviewer approval / rejection entries
- latest distinct reviewer decisions that tooling reduces into the authoritative review state

## Typical flow

```bash
# request review
scripts/request-review.sh repo-audit --note "Ready for active"

# record a reviewer decision
scripts/approve-skill.sh repo-audit --reviewer lvxiaoer --decision approved --note "Looks good"

# preview the effective active-stage quorum result
scripts/review-status.py repo-audit --as-active --require-pass

# promote after policy checks pass
scripts/promote-skill.sh repo-audit
```

## Policy expectations

The current promotion policy can require:

- `reviews.json` to exist
- reviewer identities to belong to configured policy groups
- reviewer identities distinct from the skill owner
- a stage/risk-specific minimum number of counted approvals
- coverage from required reviewer groups
- all blocking rejections to be resolved by a later distinct decision from the same reviewer

That lets promotion remain lightweight while still producing an auditable review trail.

## Review quorum

You can inspect whether a skill currently meets policy with:

```bash
scripts/review-status.py repo-audit
scripts/review-status.py repo-audit --as-active --require-pass
```

The status command counts the latest distinct decision per reviewer, ignores unconfigured reviewers, applies the current policy quorum rules, and reports missing reviewer-group coverage.

## Source of truth

`_meta.json.review_state` is still maintained for compatibility, but it is no longer authoritative. Review tooling now computes the effective review state from:

- `policy/promotion-policy.json`
- the current skill stage and risk level
- the latest distinct reviewer decisions in `reviews.json`
