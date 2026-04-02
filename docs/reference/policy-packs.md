---
audience: contributors, integrators, reviewers
owner: repository maintainers
source_of_truth: policy pack reference
last_reviewed: 2026-03-30
status: maintained
---

# Policy Packs

Policy packs let this repository compose reusable policy defaults without forcing every policy domain to live in a single top-level file.

Version 11-01 adds two new repo-local locations:

- `policy/policy-packs.json` selects the active packs in evaluation order.
- `policy/packs/<name>.json` stores each reusable JSON-only pack.

## Why this exists

Before 11-01, governance and release rules were loaded directly from one-off repository files such as:

- `policy/promotion-policy.json`
- `policy/namespace-policy.json`
- `config/signing.json`
- `config/registry-sources.json`

That kept compatibility simple, but it made policy reuse awkward because shared defaults had to be duplicated across repositories and loaders.

Policy packs add a composition layer while keeping those existing repository-local files as the final compatibility-safe override layer.

## Selection file

`policy/policy-packs.json` declares ordered `active_packs`:

```json
{
  "$schema": "../schemas/policy-pack-selection.schema.json",
  "version": 1,
  "compatibility_version": "11-01",
  "description": "Repository-local selection of additive policy packs.",
  "active_packs": ["baseline"]
}
```

Load order is deterministic:

1. active packs are loaded in listed order
2. later packs win over earlier packs
3. repository-local files win over packs

## Supported domains

11-01 policy packs can currently define only these domains:

- `promotion_policy`
- `namespace_policy`
- `signing`
- `registry_sources`
- `team_policy`
- `exception_policy`

Each pack stores those domains under a top-level `domains` object in `policy/packs/<name>.json`.

## Merge rules

Pack loading intentionally stays simple and deterministic in 11-01:

- objects deep-merge
- arrays replace, except `exception_policy.exceptions`, which merge in source order by stable `id`
- scalars replace
- later packs win over earlier packs
- repository-local files win over packs

That final rule matters most during migration: repository-local files win over packs, so existing operational entrypoints can keep reading the same effective domain shape they used before.

## Repository-local overrides

After pack composition, loaders apply the legacy repository-local files as the last override layer:

- `policy/promotion-policy.json`
- `policy/namespace-policy.json`
- `config/signing.json`
- `config/registry-sources.json`
- `policy/team-policy.json`
- `policy/exception-policy.json`

This means policy packs are additive in 11-01, not a breaking replacement for the existing files.

## Team governance scopes

Version 11-03 adds a shared `team_policy` domain so repositories can declare team membership once and reuse it across namespace and review policy.

- `policy/team-policy.json` defines named teams plus optional delegates.
- `policy/namespace-policy.json` publisher entries can now use `owner_teams`, `maintainer_teams`, `authorized_signer_teams`, and `authorized_releaser_teams`.
- `policy/promotion-policy.json` reviewer groups can now use `teams` alongside direct `members`.

That keeps delegated ownership and delegated review scopes additive: direct actor lists still work, while team-backed scopes expand into the same validation, quorum, and trace outputs.

## Break-glass exceptions

Version 11-04 adds a shared `exception_policy` domain for time-bounded promotion or release waivers.

- `policy/exception-policy.json` stores exception records with stable `id`, `scope`, exact `skills`, stable blocking `rules`, approvers, justification, and expiration.
- `uv run infinitas policy check-promotion --json --as-active <skill>` now emits top-level `exception_usage` plus `policy_trace.exceptions` when an active promotion exception waives a blocker.
- `uv run infinitas release check-state <skill> --mode preflight --json` emits the same `exception_usage` and trace details for release preflight waivers such as `dirty-worktree`.

Exceptions stay additive: promotion and release still fail exactly as before unless a matching, currently active exception record applies.

## Validation

Use the focused checker to validate the selector and every referenced pack:

```bash
uv run infinitas policy check-packs
```

`scripts/check-all.sh` now runs the same validation as part of the standard repository checks.

## Debugging policy evaluation

Version 11-02 adds additive policy-evaluation traces to the main governance entrypoints:

- `uv run infinitas policy check-promotion --json --as-active <skill>`
- `uv run infinitas release check-state <skill> --json`
- `python3 scripts/validate-registry.py --json`

Each command now emits `policy_trace` or `policy_traces` data that includes:

- the evaluated policy domain
- the allow/deny decision
- ordered `effective_sources`
- `applied_rules`
- `blocking_rules`
- `exceptions` when a break-glass waiver is actually used
- human-readable reasons and next actions

`scripts/validate-registry.py --json` also returns structured `validation_errors` entries so callers can see per-skill failures alongside namespace-policy traces.

Promotion and release JSON outputs additionally expose top-level `exception_usage` so downstream automation can distinguish waived blockers from ordinary clean passes.

When debugging interactively, use `--debug-policy` to keep the existing text output and append a rendered policy trace for the same decision.

## Deferred to 11-02

11-01 intentionally stops at structure, loading, precedence, and compatibility-safe integration.
11-02 adds decision traces and ordered source visibility, but still defers full field-level provenance.

The following are explicitly deferred to 11-02:

- remote fetching or shared hosted pack registries
- executable hooks or plugin-style policy evaluators

Policy packs remain repo-local and JSON-only in this phase.
