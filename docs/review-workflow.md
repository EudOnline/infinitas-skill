# Review Workflow

Version 7 introduces an explicit review workflow for promotion.

## Files

Each skill can keep a `reviews.json` file with:

- review requests
- approval / rejection entries

## Typical flow

```bash
# request review
scripts/request-review.sh repo-audit --note "Ready for active"

# record a reviewer decision
scripts/approve-skill.sh repo-audit --reviewer lvxiaoer --decision approved --note "Looks good"

# promote after policy checks pass
scripts/promote-skill.sh repo-audit
```

## Policy expectations

The current promotion policy can require:

- `reviews.json` to exist
- a minimum number of approvals
- reviewer identities distinct from the skill owner

That lets promotion remain lightweight while still producing an auditable review trail.
