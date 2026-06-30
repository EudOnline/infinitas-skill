---
audience: contributors, maintainers
owner: repository maintainers
source_of_truth: plans retention policy
last_reviewed: 2026-06-30
status: maintained
---

# Plans

This directory holds **dated implementation plans and design drafts**. Plans are
historical record: they capture what was intended and decided at a point in time,
not the current state of the code.

## How to read these

- A plan describes the repository **as of its date**, before and during the work.
- Code, modules, and scripts named in a plan may have since been renamed, moved,
  or removed. Do **not** treat file/identifier references inside a plan as live.
- For current architecture, see `.planning/codebase/STRUCTURE.md` and the live
  tree. For current behavior, see `docs/reference/` and `docs/guide/`.
- If a plan was superseded, its own header usually carries a `> Status: Superseded`
  note pointing at the replacement.

## Frontmatter convention

Give each plan/scorecard/spec doc a `status:` field in its frontmatter:

- `active` — currently being implemented or canonically in force
- `superseded` — replaced by a later plan (link to it)
- `legacy` — describes a state that has since materially changed (e.g. a removed
  subsystem); kept for history only

Older plans predate this convention and may omit `status:`; treat any unmarked
plan as historical.

## Archival

- When a plan is superseded or its subject is removed, either add a `status:
  superseded|legacy` note in place **or** move the file to `docs/archive/`.
- `docs/archive/` is the durable home for completed/superseded plans, audits, and
  exploratory writeups (tracked, not gitignored — see `docs/archive/README.md`).
- Do not mass-rewrite historical references inside plans to match the current
  tree; that falsifies the record. Annotate at the top instead.
