# Private-First Full Cutover Design

Date: 2026-03-29

## Goal

Replace the submission-centric hosted registry with a private-first skill library where the only primary lifecycle is:

`Skill -> Draft -> Version -> Release -> Exposure -> Review Case -> Grant / Credential -> Discovery / Install`

This cutover intentionally does not preserve the old `submissions`, `reviews`, or `jobs` product workflow. Existing install-facing registry endpoints may remain, but only as canonical private-first discovery and artifact surfaces, not as compatibility shims for the old model.

## Selected Delivery Approach

We considered three implementation routes:

1. start from current `main` and selectively port mature private-first modules from `codex/private-first-registry`
2. resume the dirty experimental worktree and merge latest `main`
3. rebuild the full private-first stack only from current `main`

The selected approach is `1`.

Why:

- current `main` already contains the latest homepage, auth-modal, i18n, and audience-aware registry fixes
- the old full-rearchitecture branch already contains useful authoring, release, access, review, and discovery modules
- the experimental worktree is dirty and includes unreviewed deletions, so wholesale merge would create avoidable risk

## Product Shape

After cutover, the hosted product is a private skill library with selective sharing and policy-gated public publication.

The operator experience becomes:

- `Skills`: top-level inventory of owned skills
- `Drafts`: mutable authoring workspaces
- `Releases`: immutable materialized artifacts
- `Share`: exposures, listing/install modes, grants
- `Review`: exposure-tied review cases and decisions
- `Access`: principals, grants, credentials, and token inspection

The old nouns `submission`, `promote`, and `publish` are removed from the main UI and operator workflow.

## Core Domain Model

### Human and machine identity

- `User` remains the hosted login record for bootstrap and browser identity
- `Principal` becomes the canonical authorization identity
- `Team`, `TeamMembership`, and `ServicePrincipal` model non-user ownership and automation
- `Credential` becomes the canonical bearer-token representation

Short-term bridge:

- browser sign-in may still resolve through `User.token`
- all registry and private API authorization resolves through `AccessContext`
- global `registry_read_tokens` stops being the primary access model

### Authoring and release

- `Skill` is the durable package identity
- `SkillDraft` is mutable and editable
- sealing a draft creates immutable `SkillVersion`
- `Release` materializes installable artifacts from one version
- `Artifact` stores manifest, bundle, signature, provenance, preview, and related immutable outputs

### Sharing and review

- `Exposure` describes audience, listing mode, install mode, review requirement, and state
- `ReviewCase` and `ReviewDecision` attach governance to exposure, not to draft content
- `AccessGrant` gives explicit entitlement for non-public sharing
- `Credential` presents access for humans, services, or grant tokens

## API and App Composition

### Canonical API namespaces

The application keeps `server/app.py` as the composition root, but the mounted API becomes private-first:

- `server/api/auth.py`
- `server/api/background.py`
- `server/modules/access/router.py`
- `server/modules/authoring/router.py`
- `server/modules/release/router.py`
- `server/modules/exposure/router.py`
- `server/modules/review/router.py`
- `server/modules/discovery/router.py`

The following routes stop being mounted:

- `server/api/submissions.py`
- `server/api/reviews.py`
- `server/api/skills.py`
- `server/api/jobs.py`
- `server/api/search.py`

### Install and discovery surfaces

Two API surfaces remain important after cutover:

1. private-first APIs under `/api/v1/...`
2. hosted registry install/discovery documents under `/registry/...`

The `/registry/...` family stays because the CLI and install flow still need a stable discovery and artifact contract. However, the payloads come only from the private-first domain model and discovery projections.

## Worker and Job Model

After cutover, the worker only processes private-first jobs.

Canonical job kinds:

- `materialize_release`
- follow-up private-first jobs added later if needed

Removed job kinds:

- `validate_submission`
- `promote_submission`
- `publish_submission`

`jobs` may remain as a technical queue table, but it is no longer a submission workflow table.

## UI Strategy

The UI will preserve the current kawaii shell, language switcher, auth modal, theme switching, and general visual system from `main`, while replacing the content architecture.

New templates:

- `skills.html`
- `skill-detail.html`
- `draft-detail.html`
- `release-detail.html`
- `share-detail.html`
- `access-tokens.html`
- `review-cases.html`

Removed templates:

- `submissions.html`
- `reviews.html`
- `jobs.html`

The homepage still acts as an entrypoint, but its maintainer navigation and console links point into the new private-first lifecycle instead of the old submission console.

## Data Migration and Schema Direction

This cutover no longer treats `submissions`, `reviews`, and old publish jobs as compatibility tables for product behavior.

Schema direction:

1. extend the current partial private-first schema to the canonical full-domain shape
2. add principals, teams, service principals, review policies, review decisions, and audit events
3. replace simple grant/credential tables with the canonical grant/credential model
4. change `jobs` to reference `release_id` rather than `submission_id`
5. drop `submissions` and `reviews`

We will keep downgrade stubs where practical, but the forward path is the only supported runtime model.

## Cutover Rules

- no new code should call submission lifecycle services
- no new UI should render submission/review/job pages
- no new install path may depend on legacy submission state
- discovery, access checks, and install resolution must depend on release/exposure/grant state only
- public exposure must remain blocking-review only
- private and grant exposure may activate without review unless policy requires otherwise

## Verification Strategy

The cutover is considered complete when all of the following are true:

1. the app boots through Alembic with the canonical private-first schema
2. old submission/review routes are not mounted
3. draft sealing, release materialization, exposure creation, review decisioning, and grant-token install flows work end-to-end
4. `/registry/...` payloads are built from private-first discovery projections only
5. hosted UI pages for skills, releases, sharing, access, and review render correctly in the kawaii shell
6. legacy compatibility tests are removed or replaced by private-first equivalents

## Implementation Notes

- Reuse the committed module work from `codex/private-first-registry` where it is structurally sound.
- Rebuild `server/app.py`, `server/auth.py`, and the hosted templates against current `main` so we keep the latest UI/auth/i18n fixes.
- Prefer one-way cutover edits over dual-path conditionals. If both old and new paths exist in the same function, bias toward deleting the old path rather than abstracting both.
