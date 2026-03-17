# Review Workflow

Version 7 introduces an explicit review workflow for promotion.

## Files

Each skill keeps review evidence in:

- `reviews.json` for local review requests plus repo-recorded reviewer decisions
- optional `review-evidence.json` for normalized imported platform approvals or rejections
- a computed latest-distinct decision set that tooling reduces into the authoritative review state across both files

## Typical flow

```bash
# request review
scripts/request-review.sh repo-audit --note "Ready for active"

# optionally import normalized platform-native approvals or rejections
python3 scripts/import-platform-review-evidence.py repo-audit --input /tmp/review-evidence.json --json

# record a reviewer decision
scripts/approve-skill.sh repo-audit --reviewer lvxiaoer --decision approved --note "Looks good"

# inspect deterministic reviewer suggestions before or after requesting review
python3 scripts/recommend-reviewers.py repo-audit --as-active --json
scripts/request-review.sh repo-audit --note "Ready for active" --show-recommendations

# preview the effective active-stage quorum result
scripts/review-status.py repo-audit --as-active --require-pass
scripts/review-status.py repo-audit --as-active --json --show-recommendations

# promote after policy checks pass
scripts/promote-skill.sh repo-audit
```

## Policy expectations

The current promotion policy can require:

- `reviews.json` to exist
- reviewer identities to belong to configured policy groups
- reviewer groups to resolve through shared teams declared in `policy/team-policy.json`
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

In `--json` mode, each latest decision keeps its evidence provenance:

- `source`
- `source_kind`
- `source_ref`
- `url`

When a reviewer group uses `teams`, the same command still reports coverage by group name; team membership simply becomes the source of who is allowed to satisfy that group.

## Imported evidence

`review-evidence.json` is additive input, not a replacement for `reviews.json`.

- it lives next to the skill metadata as a sibling file
- each entry must declare `source`, `source_kind`, `source_ref`, `reviewer`, `decision`, and `at`
- duplicate reviewer identities inside imported evidence fail validation instead of being silently merged
- the latest reviewer decision still resolves deterministically by reviewer and timestamp across local plus imported entries

Use `python3 scripts/import-platform-review-evidence.py <skill> --input <path> --json` when an approval happened on another platform but still needs to count toward Git-native quorum evaluation.

Imported evidence also flows through:

- `scripts/check-promotion-policy.py --json`
- `scripts/check-release-state.py --json`
- `scripts/build-catalog.sh`

Those surfaces preserve imported provenance fields so operators can see whether quorum passed because of repo-local review entries or imported platform evidence.

## Advisory reviewer guidance

Reviewer suggestions are deterministic and read-only:

- `python3 scripts/recommend-reviewers.py <skill> --as-active --json` returns grouped candidate reviewers plus escalations
- `scripts/request-review.sh <skill> --show-recommendations` prints the same guidance next to the review request
- `python3 scripts/review-status.py <skill> --as-active --json --show-recommendations` embeds the recommendation payload alongside the computed quorum result

The recommendation payload explains exclusions such as `owner-conflict` and `already-counted-reviewer`, and emits escalation guidance when no eligible reviewer can satisfy one required group.

## Source of truth

`_meta.json.review_state` is still maintained for compatibility, but it is no longer authoritative. Review tooling now computes the effective review state from:

- `policy/promotion-policy.json`
- the current skill stage and risk level
- the latest distinct reviewer decisions merged from `reviews.json` and `review-evidence.json`
