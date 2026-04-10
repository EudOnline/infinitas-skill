---
audience: frontend maintainers, delegated implementation agents
owner: repository maintainers
source_of_truth: kimi frontend execution brief
last_reviewed: 2026-04-08
status: maintained
---

# Kimi Frontend Execution Brief

Use this brief when delegating the frontend follow-up work to Kimi Code.

Do not redesign the UI. Preserve the current visual language, layout style, component tone, spacing rhythm, and interaction patterns already established in the hosted control plane.

## Objective

Bring the frontend into alignment with the now-stable OpenClaw-first backend contract.

The backend has already been migrated so that:

- OpenClaw is the canonical runtime model
- release readiness blocks on canonical OpenClaw runtime freshness, not triple-platform parity
- public, me, and grant search results all expose runtime metadata
- hosted registry `ai-index` and `discovery-index` now expose OpenClaw runtime fields
- skill contract validation now prefers `verification.required_runtimes`

Your job is to update frontend behavior and data consumption without changing the UI style.

## Non-negotiable constraints

- Do not change the existing UI visual style
- Do not introduce a new design system
- Do not rename backend endpoints
- Do not invent shortcut endpoints
- Do not treat `required_platforms` as the preferred runtime field name in new UI
- Do not block UI flows on stale Codex or Claude historical evidence alone

## Backend fields to treat as primary

### Search and discovery

These fields are now safe to consume from public, me, and grant search results:

- `runtime`
- `runtime_readiness`
- `workspace_targets`
- `install_scope`
- `install_ref`
- `install_api_path`

Preferred display behavior:

- use `runtime_readiness` for readiness badges
- use `workspace_targets` for concise install-location hints
- use `runtime.platform` to label OpenClaw-native items

### Release readiness

For release state views, use:

- `release.platform_compatibility.canonical_runtime_platform`
- `release.platform_compatibility.canonical_runtime`
- `release.platform_compatibility.blocking_platforms`
- `release.platform_compatibility.verified_support`

Preferred display behavior:

- show blocking status from `canonical_runtime` and `blocking_platforms`
- treat `verified_support` as historical context
- do not present historical Codex or Claude rows as the primary release blocker

### Skill contract validation

For OpenClaw skill validation or authoring-facing contract displays, prefer:

- `verification.required_runtimes`
- `verification.smoke_prompts`
- `verification.legacy.required_platforms`

Preferred display behavior:

- primary label: required runtimes
- secondary or migration-only label: legacy required platforms

## Frontend tasks to execute

### Task 1: normalize search result rendering

Relevant areas:

- `server/static/js/app.js`
- search result cards, install panels, quick search overlays, or similar UI surfaces

What to do:

- render readiness badges from `runtime_readiness`
- surface `workspace_targets` in install-oriented search cards or detail drawers
- keep public, me, and grant search result rendering logic aligned
- ensure no search scope silently drops runtime metadata

Acceptance:

- public search result shows runtime/readiness when present
- me search result shows the same runtime/readiness fields
- grant search result shows the same runtime/readiness fields

### Task 2: normalize release-readiness rendering

Relevant areas:

- release detail page
- share/exposure page
- any release policy or preflight panels in the UI

What to do:

- read OpenClaw blocking state from `canonical_runtime` and `blocking_platforms`
- demote historical compatibility evidence to a secondary section
- update copy so the primary gate is clearly OpenClaw runtime readiness

Acceptance:

- release UI highlights OpenClaw as the maintained runtime gate
- stale Codex or Claude rows can be shown, but not as the main blocker

### Task 3: normalize skill contract rendering

Relevant areas:

- skill validation views
- authoring helpers
- any contract preview or import/export preview UI

What to do:

- prefer `verification.required_runtimes`
- if legacy info is shown, label it as legacy or migration metadata
- avoid rendering `required_platforms` as the primary heading in new UI

Acceptance:

- OpenClaw validation UI uses “required runtimes” wording first
- legacy required platforms are visibly secondary

### Task 4: keep lifecycle actions aligned

Relevant areas:

- skill detail
- draft detail
- release detail
- share/exposure detail
- review case views

What to do:

- preserve current lifecycle write-path work already planned in the frontend checklist
- when showing install or runtime hints, use the new OpenClaw-first fields instead of compatibility-era guesses

Acceptance:

- no frontend code invents compatibility-first logic that disagrees with the backend

## Files to use as backend contract references

- `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/guide/frontend-control-plane-alignment.md`
- `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/docs/guide/frontend-control-plane-checklist.md`
- `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/api/search.py`
- `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/server/modules/registry/service.py`
- `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/openclaw/skill_contract.py`
- `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/src/infinitas_skill/release/service.py`

## Suggested implementation order

1. Update search result rendering for public, me, and grant scopes
2. Update release readiness / share UI to use canonical OpenClaw gate fields
3. Update skill contract or validation UI to prefer `required_runtimes`
4. Run only targeted frontend verification without visual redesign

## Required final report from Kimi

When implementation is done, Kimi should report:

- which frontend files changed
- which backend fields are now consumed
- whether any frontend code still reads `required_platforms` as a primary field
- whether any UI surface still treats Codex or Claude historical evidence as a release blocker
