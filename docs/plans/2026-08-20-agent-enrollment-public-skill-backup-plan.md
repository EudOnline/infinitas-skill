---
audience: contributors, maintainers, security reviewers, operators
owner: repository maintainers
source_of_truth: agent enrollment and public skill backup implementation plan
last_reviewed: 2026-08-20
status: active
---

# Agent Enrollment And Public Skill Backup Implementation Plan

## Goal

Replace direct namespace publisher-token issuance with an approval-based Agent enrollment flow.
After approval, each Agent has an independent service identity and credential, can publish validated
immutable Skill Releases under its own namespace, and defaults those Releases to public visibility.
Public Skills are anonymously discoverable and installable; consumers can update their local
installation without receiving permission to modify the publisher's Skill.

This is a hard product cutover. The project is not deployed, so this plan does not preserve the old
namespace-token UI, API, configuration, schema, CLI defaults, or private-first compatibility layers.

## Audited Corrections To The Initial Proposal

The initial proposal had the correct product direction but required the following corrections before
implementation:

1. **Do not place the final Agent API key in the copied prompt.** The prompt contains a short-lived,
   one-use enrollment key. The Agent generates its final `agt_...` key locally and sends only a
   SHA-256 verifier with its application. Approval activates that verifier as a Credential. The
   final key is never returned by the server or stored in plaintext.
2. **Do not model an Agent as a delegated administrator token.** The current namespace token binds
   `principal_id` and `product_scope_id` to the issuing user's Principal. Every approved Agent must
   instead receive its own `Principal(kind="service")` and `ServicePrincipal`.
3. **Do not require a User row for Agent publication.** Release creation and background-job
   attribution must accept a service Principal. Authorization comes from Principal ownership,
   Credential scopes, Credential policy, and ServicePrincipal state, not from a synthetic User.
4. **Separate Agent approval from content review explicitly.** Approval grants a policy capability
   such as `auto_public_publish`. When enabled, compatible Releases can activate a public Exposure
   without a second human decision. This is a publisher-trust decision, not a claim that every Skill
   is safe. Automated validation, secret scanning, quotas, provenance, and audit remain mandatory.
5. **Define public as anonymous read.** Configuring a global reader token must not turn public
   metadata or public artifacts into authenticated resources. This plan removes the global Registry
   reader-token gate; private and grant content continue to require scoped credentials.
6. **Define update narrowly.** Any consumer may update its local installation to a newer public
   immutable Release. It may not overwrite or publish a new version of another Agent's Skill.
   Cross-Agent authoring is out of scope for this cutover: another Agent may only read public
   Releases and update its local installation. Existing ChangeSets remain an owner/maintainer
   collaboration mechanism and are not a workaround or acceptance path for Agent-to-Agent writes.
7. **Keep program backup and runtime-data backup separate.** Public Skill backup contains program
   files only. Runtime/business data remains an encrypted off-host snapshot and is never made public.
8. **Make enrollment consumption atomic.** An invitation is single-purpose, single-use, expiring,
   rate-limited, and consumed in the same transaction that creates the pending application.
9. **Keep browser and Agent surfaces separate.** Human actions use Session Cookie + CSRF under
   `server/ui/routes/`; Agent enrollment and operation use JSON response models under
   `server/modules/identity/agent_router.py`. Neither route layer imports the other.
10. **Edit the sole initial migration.** Add the new current schema to
    `alembic/versions/0001_initial.py`; do not add a migration chain or legacy data adaptation.

### Second audit findings applied to this plan

The first draft was re-audited against the live authorization, Registry, CLI, and content-validation
code. The following findings are binding design corrections, not optional implementation details:

| Severity | Finding | Required plan correction |
|---|---|---|
| High | Putting `enroll_...` in a generated shell command leaks it to shell history, process listings, and Agent tool logs. | The prompt invokes `infinitas agent join --base-url <url> --enrollment-token-stdin`; the raw invitation is supplied only through stdin (or an explicitly protected `0600` input file created by the Agent). No secret-bearing argv form is implemented or documented. |
| High | The current ChangeSet API authorizes against the Skill namespace and cannot accept a different Agent without a contributor-grant model; treating it as the cross-Agent acceptance path would either fail or impersonate the owner. | Remove that acceptance scenario. Cross-Agent authoring requires a future contributor-grant design; this release only supports public read/local update and owner/maintainer writes. |
| High | The current Release route requires `context.user` and the current Exposure routes require `exposure:write`; simply issuing an Agent the legacy publisher scope will make public backup fail, while granting that scope lets the Agent directly manipulate visibility. | Define a server-side Agent publish orchestration that materializes/attests the Release and evaluates `auto_public_publish` from the Credential policy. Agent credentials need publish capability but no generic exposure-admin capability; direct Exposure create/patch/activate/revoke remains maintainer/owner-only. |
| High | The existing scope sets are inconsistent: publisher tokens get `release:write`/`exposure:write`, but authoring/release routes each check different literals. | Publish an explicit capability matrix for `agent_token`, personal/session, and delegated credentials, then make every authoring/release/job path call the same capability service. Tests must prove an Agent can complete its own pipeline without gaining exposure administration or review decisions. |
| High | `authenticated` release access currently checks only `context.user`, so a service Principal Agent cannot consume that audience even when approved. | Define authenticated access as an active authenticated Principal (user or approved, non-suspended Agent) and test both identities. Public remains anonymous; this change must not make pending/suspended/revoked Agents authenticated. |
| High | Current policy parsing has no `auto_public_publish` capability, and publish quota keys are credential IDs. A key rotation could therefore lose the public-trust policy or reset the daily quota. | Store the approved public-publish capability and quota at the Agent/ServicePrincipal policy boundary, make replacement Credentials inherit it, and meter quota by ServicePrincipal (with an atomic daily counter), not by rotatable Credential ID. Only maintainers may change that policy. |
| High | A public-by-default publisher can expose credentials if path filtering is treated as complete content security. | Require both path policy and canonical bundle content scanning. The scanner must reject the checked-in secret signatures/private-key material listed by the validation contract, including files explicitly allow-listed by path; unknown/failed scans fail closed. |
| High | The live path policy does not currently treat `.env` or arbitrary credential/config files as sensitive, while the content signature list only covers known token families. | Add an explicit deny list for dotenv files, shell histories, credential/config filenames, and private-key material, then run extensible content scanning over all included files. A generic `KEY=value` file or an unrecognized secret signature must not become public merely because its path is not currently known. |
| High | One-time HTML containing an invitation secret can be cached or re-read through browser history, refresh, analytics, or an accidental redirect. | The result response is `Cache-Control: no-store`, has no secret-bearing URL, emits no analytics/audit secret, uses a one-time POST result, and never offers a later raw-secret retrieval endpoint. |
| Medium | “Fingerprint” was undefined and could be mistaken for device attestation. | Define it as a displayed, truncated fingerprint of the submitted Agent Credential verifier. Runtime/platform/capability fields are self-reported metadata; neither is remote device proof. The fingerprint is for human comparison only. |
| Medium | `restore <publisher/skill>` has no Registry location when no profile exists. | Require an explicit `--registry <profile>` or `--base-url` for restore/update/verify when no default public profile is configured. Document the anonymous public bootstrap command and test a fresh second workspace. |
| High | The current HTTP Registry client permits `http://` and follows redirects; anonymous public artifacts would otherwise be vulnerable to origin downgrade or trust-source substitution. | Require HTTPS for non-test public Registry origins, pin the configured origin after bootstrap, reject cross-origin and scheme-downgrade redirects, and fail closed when trust material or signer policy changes unexpectedly. |
| High | `SELECT ... FOR UPDATE` is not a portable single-use guarantee for the project's supported SQLite path. Two enrollment requests could both observe an open invitation. | Consume through a conditional state transition (`UPDATE ... WHERE state='open' AND expires_at>now`) and require exactly one affected row, backed by unique constraints. Approval/recovery uses the same compare-and-swap pattern and conflict re-read; correctness must not depend on row locks. |
| Medium | `0600` alone does not protect a profile from symlink, partial-write, or directory-permission failures. | Use a fixed platform config root (`0700`), reject symlinked profile paths, atomically create/replace with `0600`, fsync file and directory, and never overwrite an existing valid key during interrupted recovery. |
| Medium | Losing the status key currently has no defined recovery path. | After approval, the Agent may probe `/access/me` with its locally retained API key; before approval it must restart with a new invitation. `status` loss never causes the server to return or regenerate the API key. |

## Product Semantics

### Agent identity

An approved Agent owns one stable service namespace. Its Skill names are qualified by that namespace:

```text
agent-alpha/pdf-reader
agent-beta/pdf-reader
```

Agent slug reuse is forbidden while a namespace reservation is active or an Agent has ever been
approved, so audit identities remain unambiguous. A reservation may issue sequential replacement
invitations after expiry/revocation/rejection, but never two live invitations or pending enrollments
at once. A reservation that never produced an approved Agent may be explicitly released by a
maintainer through a recorded action; this permits correcting a mistyped slug without making an
approved namespace reusable. A maintainer can inspect all Agent namespaces; an Agent can mutate only
its own Skills.

### Visibility

| Visibility | Discovery and download | Write authority |
|---|---|---|
| `public` | Anonymous | Owning approved Agent or maintainer |
| `authenticated` | Any active approved Agent | Owning approved Agent or maintainer |
| `grant` | Explicit scoped grant | Owning approved Agent or maintainer |
| `private` | Owner and maintainer | Owning approved Agent or maintainer |

New Agent backups default to `public + listed + enabled`. Public availability does not grant publish,
archive, visibility-change, token-issuance, or ChangeSet-acceptance authority.

### Backup and restore

- **Skill backup** means validate, normalize, package, upload, version, materialize, attest, and expose
  a Skill program as an immutable Release.
- **Skill restore** means resolve an exact trusted Release, verify manifest/digest/provenance, stage it,
  and atomically install it into a target Skill directory.
- **Skill update** means resolve a newer Release from the recorded Registry and update the local
  installation while retaining rollback history.
- **Runtime-data backup** remains the existing encrypted OpenClaw snapshot workflow. It is not folded
  into a public Skill Release.

## Enrollment Security Protocol

### Secrets

The flow uses three separate values:

| Value | Generated by | Purpose | Server storage |
|---|---|---|---|
| `enroll_...` invitation key | Server | Submit exactly one application | SHA-256 hash only |
| `status_...` status key | Agent | Poll the pending application | SHA-256 hash only |
| `agt_...` final API key | Agent | Bearer authentication after approval | SHA-256 hash only |

The Agent must persist `status_...` and `agt_...` outside the workspace with mode `0600` before
submitting the application. The application sends their verifiers, never their raw values. The
`agt_...` verifier is already the canonical `sha256:<hex>` value consumed by the existing bearer
resolver; approval stores that verifier directly and must not hash it a second time. A leaked
database therefore does not reveal any usable key. A leaked invitation can at most race one pending
application before expiry; the administrator must compare the expected Agent label, reported runtime,
and Credential fingerprint before approval. Define the fingerprint exactly as the first 16 lowercase
hex characters of `SHA-256("infinitas-agent-fingerprint-v1\\0" + canonical_verifier)`. It must be
shown by both the applying Agent and the Web console. It is not a secret and only detects an
accidental/raced verifier mismatch. Runtime, platform, version, and capability fields are
self-reported; this protocol provides no device identity or remote attestation.

If the status key is lost while the application is pending, the pending application cannot be
recovered and the maintainer must revoke/reject it before issuing a replacement invitation against
the same unclaimed reservation. If it is lost
after approval, the Agent probes `/api/v1/access/me` with its retained final API key and reconstructs
only non-secret status metadata. The server never returns, rotates, or regenerates the final API key
as part of status recovery.

### State machines

```text
AgentNamespaceReservation: reserved -> claimed
                                    -> released

AgentInvitation: open -> consumed
                       -> expired
                       -> revoked

AgentEnrollment: pending -> approved
                         -> rejected

ServicePrincipal: active -> suspended -> active
                         -> revoked
```

Terminal invitation/enrollment states cannot be reopened. Rejection requires a replacement invitation
under the same unclaimed reservation. Agent revocation permanently
revokes every Agent credential but leaves immutable Releases and audit history intact. Public Exposure
withdrawal is an independent explicit admin action.

### Enrollment request sequence

1. A maintainer creates a dedicated invitation with a reserved Agent slug, display name, expiry, quota,
   allowed object kinds, and public-publish policy.
2. The server returns the raw invitation key and a self-contained prompt exactly once. The prompt
   instructs the Agent to invoke `infinitas agent join --base-url <url> --enrollment-token-stdin` and
   supply the embedded one-use invitation through stdin without echo. The secret is never placed in
   argv, an environment variable, a URL, or a generated shell command. A protected `0600` input file
   may be used only when stdin is unavailable and must be removed immediately after consumption. The
   copied prompt necessarily contains the invitation, so its short expiry and single-use semantics
   remain security boundaries; the Agent never needs a human to transcribe the final API key.
3. The Agent runs `infinitas agent join`, generates status/API keys locally, stores them safely, and
   submits their verifiers plus runtime metadata. It returns the non-secret enrollment public ID and
   Credential fingerprint to the human who supplied the prompt; it never echoes any raw key.
4. The server atomically consumes the invitation with a conditional state transition and creates one
   `pending` enrollment under database uniqueness constraints.
5. The Agent polls with its status key. Pending credentials cannot authenticate normal APIs.
6. A maintainer approves or rejects the enrollment. Approval transactionally creates the service
   Principal, ServicePrincipal, and active Agent Credential using the submitted API-key verifier. The
   UI requires confirmation that the public ID and fingerprint match the applying Agent's response;
   self-reported name/runtime metadata alone is insufficient.
7. The Agent observes `approved`, verifies its locally held API key through `/api/v1/access/me`, and
   bootstraps the Registry trust policy.

## Domain Ownership And Schema

### Identity domain

Add to `server/modules/identity/models.py`:

- `AgentNamespaceReservation`
  - unique reserved Agent slug and display-name baseline
  - `reserved|claimed|released` state
  - creating/releasing maintainer Principal and timestamps
  - claimed ServicePrincipal ID when approved
- `AgentInvitation`
  - random public ID
  - namespace reservation ID and requested display name
  - `enroll|recover` purpose and optional existing ServicePrincipal target
  - invitation-key hash
  - policy snapshot JSON
  - state, expiry, consumed timestamp
  - creating maintainer Principal
- `AgentEnrollment`
  - random public ID and one-to-one invitation ID
  - status-key hash and proposed Agent API-key hash
  - runtime/platform/version/capability metadata
  - pending/approved/rejected state
  - decision actor, note, and timestamps
- extend `ServicePrincipal`
  - enrollment ID
  - `active|suspended|revoked` state
  - approved and revoked metadata

An `enroll` invitation targets an unclaimed reservation and approval creates the service identity. A
`recover` invitation targets one existing active/suspended ServicePrincipal and approval atomically
installs the proposed replacement Credential and revokes the lost Credential(s); it never creates a
Principal, changes namespace ownership, or revives a revoked Agent.

Agent slug reservation is enforced at enrollment-invitation creation through the dedicated reservation record.
Open/consumed invitations and all approved enrollments retain their reservation. After an invitation
expires, is revoked, or its enrollment is rejected, a maintainer may issue one replacement invitation
against the same unclaimed reservation. A maintainer may release only a reservation with no open
invitation, pending enrollment, or approved Agent; release is audited and terminal for that record.
Approval atomically claims the reservation forever. The identity service owns invitation creation,
prompt construction, application submission, approval,
rejection, suspension, resumption, revocation, and Credential activation.

### Access domain

Agent credentials use explicit `type="agent_token"`, namespace publisher scope, and policy fields:

- `readonly=false`
- `allowed_object_kinds=["skill"]`
- `max_daily_publishes`
- `auto_public_publish=true` by default
- optional expiration

The policy is owned by the Agent/ServicePrincipal enrollment, not by a client-editable Credential
request. Replacement and recovery Credentials inherit the same server policy. Daily publish quota is
consumed against the ServicePrincipal identity, so rotation cannot reset it; maintainers may change
the policy through an audited console action. Agents cannot self-enable public publishing or increase
their quota.

The Agent capability matrix is explicit:

| Operation | `agent_token` authority |
|---|---|
| Inspect own identity/effective policy | Allowed |
| Create Skill, content, and immutable version | Own namespace only |
| Finalize publication | Own version through `/api/v1/agent/versions/{id}/publish` only |
| Read own Release/job status | Allowed |
| Read public Registry | Anonymous path; no special authority |
| Read `authenticated` Registry content | Allowed only while Agent is active |
| Create/patch/activate/revoke arbitrary Exposure | Denied |
| Decide Review Cases or change its trust policy | Denied |
| Issue object/namespace tokens or administer Agents | Denied |

Authorization must recognize Agent credentials by capabilities and product scope rather than relying
on the literal legacy `product_token` type. The credential's Principal and namespace scope are the
same Agent service Principal.

### Jobs domain

Replace `requested_by_user_id` with `requested_by_principal_id`. Job attribution must work for users,
service Principals, and system work without a synthetic User relationship.

### Release publication intent

The release domain persists one server-derived Agent publish intent per immutable Skill version (or
equivalent unique Release key). It records requesting Principal/Credential, approved-policy snapshot,
quota-consumption identity, target `public + listed + enabled`, state, and timestamps. No client field
can alter the target visibility or auto-activation decision.

Creating the Release, intent, first quota consumption, and materialization Job is one idempotent
transaction. The worker may materialize/sign the Release, but before creating the public Exposure it
must re-read the ServicePrincipal state and current effective policy. If the Agent was suspended,
revoked, or lost `auto_public_publish`, the ready Release remains unexposed and the intent records a
blocked terminal/retryable reason. Job replay and HTTP retry cannot create duplicate Releases,
Exposures, intents, or quota charges.

### Migration

Update `alembic/versions/0001_initial.py` so a clean database exactly matches `Base.metadata`. Do not
create `0002`, copy data, retain old columns, or support an old database.

## Route Contract

### Human admin HTML routes

All routes require maintainer Session Cookie and CSRF:

- `GET /agents`
- `POST /agents/invitations`
- `POST /agents/invitations/{invitation_id}/revoke`
- `POST /agents/reservations/{reservation_id}/release`
- `POST /agents/enrollments/{enrollment_id}/approve`
- `POST /agents/enrollments/{enrollment_id}/reject`
- `POST /agents/{agent_id}/suspend`
- `POST /agents/{agent_id}/resume`
- `POST /agents/{agent_id}/revoke`
- `POST /agents/{agent_id}/recovery-invitations`

The invitation POST renders a one-time result page containing the prompt. It must not put the raw
invitation key in a redirect URL, query string, log, audit payload, analytics event, or later listing.
The response sets `Cache-Control: no-store` and restrictive referrer policy. The form carries a
server-issued single-use idempotency nonce: refreshing or replaying the POST must not create another
invitation and must not return the raw key again. There is no endpoint to retrieve it later, and the
copy control must not send clipboard contents to telemetry.

### Agent JSON routes

- `POST /api/v1/agent-enrollments`
  - `Authorization: Bearer enroll_...`
  - body includes status/API-key verifiers and runtime metadata
  - returns `201` and pending enrollment metadata
- `GET /api/v1/agent-enrollments/{public_id}`
  - `Authorization: Bearer status_...`
  - returns pending/approved/rejected state without the Credential hash
- `GET /api/v1/access/me`
  - normal `Authorization: Bearer agt_...`
  - returns the service Principal identity and effective scopes
- `POST /api/v1/agent/versions/{version_id}/publish`
  - normal `Authorization: Bearer agt_...`
  - creates/reuses the Agent-owned Release, persists a server-derived public publish intent, and
    enqueues materialization/signing
  - does not accept audience, listing, install, review, or `auto_activate` fields from the Agent
  - is the only Agent publication finalization endpoint; generic Exposure-admin routes remain
    unavailable to `agent_token`
  - first request returns `202`; an idempotent retry reports the existing Release/intent without
    consuming quota again

Enrollment errors use stable meanings:

- `400`: malformed verifier or runtime metadata
- `401`: invalid invitation/status key
- `409`: consumed invitation, duplicate application, slug collision, or terminal transition
- `410`: expired or revoked invitation
- `429`: enrollment or polling rate limit

Every JSON route declares a Pydantic response model and is reflected in `openapi.json`.

## Web Console Contract

Add a dedicated Agents page rather than extending the generic Token table. Its unframed page sections
are:

1. Pending applications, ordered oldest first, with expected identity, runtime, fingerprint, age, and
   approve/reject actions.
2. Active Agents with state, scopes, last use, published Skill count, latest backup, suspend/revoke.
3. Invitation form with fixed slug, display name, expiry, publish quota, and an explicit
   "allow automatic public backups" checkbox enabled by default.
4. One-time prompt result with copy action and warnings that the invitation is temporary and the Agent
   must not echo secrets.

The pending view labels the fingerprint as an API-key fingerprint and labels runtime/capabilities as
Agent-reported. Approval text states that enabling automatic public backups is continuing trust in the
publisher, not human review of each future Release. Validation, canonical secret scanning, size and
quota limits, compatibility checks, provenance, and signing still apply. Suspension/revocation stops
future writes but does not silently withdraw already-public Releases.

Approval requires the maintainer to enter/confirm the enrollment public ID and Credential fingerprint
reported by the applying Agent. The server compares them to the pending record and rejects a mismatch;
the Web page must not silently prefill both values from its own record because that would make the
comparison meaningless.

Do not expose internal Credential, Exposure, or Review Case vocabulary as primary UI labels. Use
Agent, invitation, request, API key, public backup, and activity.

## CLI Contract

Add a canonical `infinitas agent` command group:

```text
infinitas agent join
infinitas agent status
infinitas agent backup <skill-dir> --version <semver>
infinitas agent restore <publisher/skill> [--version <semver>]
infinitas agent update <publisher/skill>
infinitas agent verify <publisher/skill>
```

`join` stores a named Agent connection profile and secrets outside the repository, mode `0600`.
Existing Registry commands first resolve the workspace Registry source, then use the non-secret Agent
profile name referenced by that source when authenticated access is required. Anonymous public sources
use no credential. The Agent API key has no environment-variable fallback.
The containing platform configuration directory is mode `0700`; profile names cannot supply paths.
Profile writes reject symlinked targets, use a same-directory temporary file, fsync, atomically
replace, fsync the directory, and preserve any existing valid key if an operation is interrupted.
Enrollment secrets are accepted only from hidden stdin or an explicitly protected `0600` input file;
there is no secret-bearing argv or environment-variable option. The final Agent API key is never
printed, including in JSON/debug/error output.

This machine-level Agent connection profile contains only the control-plane base URL, Agent identity metadata,
and Agent credential. It is distinct from the existing workspace-level Registry source and public
trust configuration under `<repo>/config/`: `join` may offer to bootstrap that workspace after
approval, but it must not copy the Agent API key into repository files or environment-variable
references. Anonymous consumers create only the workspace-level public source/trust configuration.

`restore`, `update`, and `verify` resolve the Registry from the selected/default profile. With no
configured default they require `--registry <profile>` or `--base-url <url>` and fail with a clear
configuration error. An anonymous consumer starts with `infinitas registry bootstrap <profile>
--base-url <url>`; no Agent enrollment or reader token is required for public content.

Public Registry bootstrap requires HTTPS except for explicit loopback/test mode. It records the
canonical origin with the workspace source and rejects scheme downgrade, cross-origin redirects, and
silent trust/signer replacement. A trust change requires an explicit maintainer/user re-trust action;
`update` never accepts new signing roots simply because the Registry serves them.

`backup` is a high-level, public-by-default orchestration of the existing hosted publish pipeline. It
must run sensitive-path checks and display the included/excluded inventory before writes. The server
then canonicalizes the uploaded bundle and independently runs content signature scanning across every
included regular file, including path-allow-listed files. A scanner error or unreadable file fails
closed; an allow-list can suppress a path-policy block but cannot suppress secret-content detection.
`restore`,
`update`, and `verify` reuse the existing installer, manifest, integrity, and rollback services rather
than implementing new extraction logic.

The existing `infinitas openclaw skill backup/restore` commands retain their distinct encrypted
program-plus-runtime-data meaning and must be documented separately to prevent accidental public data
publication.

## Implementation Tasks

### Task 1: Freeze The Revised Product And Security Contract

**Files:**

- Create: `docs/adr/0004-agent-enrollment-and-public-registry.md`
- Modify: `docs/specs/web-admin-agent-product-contract.md`
- Modify: `docs/guide/agent-collaboration-and-private-data.md`
- Modify: `docs/ops/openclaw-skill-backup.md`
- Modify: `docs/reference/configuration.md`
- Test: `tests/integration/test_reference_docs.py`

**Steps:**

1. Add failing contract tests for independent Agent identity, anonymous public read, public-by-default
   backup, local API-key generation, and runtime-data separation.
2. Record the hard cut from direct namespace tokens and private-first defaults in ADR 0004.
3. Update the maintained product spec; leave historical dated plans unchanged.
4. State that Agent approval can grant automatic public publishing and that this is a trust decision.
5. Run the reference-doc tests.

**Exit criteria:** Maintained docs have one non-conflicting Agent/public contract and distinguish Skill
program Releases from encrypted data snapshots.

### Task 2: Add Enrollment Models To The Single Current Schema

**Files:**

- Modify: `server/modules/identity/models.py`
- Modify: `server/model_registry.py`
- Modify: `server/modules/jobs/models.py`
- Modify: `server/modules/release/models.py`
- Modify: `alembic/versions/0001_initial.py`
- Test: `tests/unit/server/test_model_imports.py`
- Test: `tests/integration/test_alembic_metadata.py`

**Steps:**

1. Add failing metadata and clean-upgrade tests for the enrollment tables, ServicePrincipal state, and
   Principal-owned Jobs plus the unique Agent publish-intent persistence.
2. Define the identity-owned models and constraints, including one enrollment per invitation and a
   unique Agent namespace reservation. Enforce at most one open invitation/pending enrollment per
   reservation and permanent non-reuse after it is claimed by an approved Agent.
3. Replace Job user ownership with Principal ownership and update ORM relationships.
4. Edit `0001_initial.py` to match the ORM exactly.
5. Run isolated model imports, Alembic upgrade, and `alembic check` tests.

**Exit criteria:** A new database contains only the current schema and `alembic check` reports no diff.

### Task 3: Implement The Enrollment State Machine And Secret Handling

**Files:**

- Create: `server/modules/identity/agent_schemas.py`
- Create: `server/modules/identity/agent_service.py`
- Test: `tests/unit/server_identity/test_agent_enrollment.py`
- Test: `tests/security/test_agent_enrollment_security.py`

**Steps:**

1. Write failing tests for expiry, revocation, replay, duplicate submission, verifier validation,
   concurrent consumption, illegal transitions, Credential fingerprint consistency, status-key loss,
   and secret redaction.
2. Implement invitation/status prefix validation and SHA-256 verifier normalization.
3. Consume invitations with a database-portable compare-and-swap update from `open` to `consumed`,
   require exactly one affected row, and create the uniquely constrained pending enrollment in the
   same transaction. Do not rely on `SELECT ... FOR UPDATE`, which is insufficient on SQLite.
4. Approve with a conditional `pending` transition and uniqueness constraints: create Principal,
   ServicePrincipal, claim the namespace reservation, and create the Agent Credential from the
   proposed verifier in one transaction. A conflicting worker re-reads the terminal result. Reject
   without creating any Principal or Credential.
5. Implement suspension checks in credential resolution and permanent revocation of all Agent
   credentials.
6. Emit redacted audit events for every transition.
7. Treat runtime/capability data as untrusted display metadata and derive the displayed Credential
   fingerprint server-side from the submitted verifier.
8. Permit a serialized replacement invitation against an unclaimed reservation after terminal
   failure, and permit explicit release only when no open/pending/approved dependency exists.
9. Distinguish enrollment from recovery approval: recovery is permitted only for an existing
   active/suspended Agent and replaces Credentials without creating or reclaiming identity rows.

**Exit criteria:** No raw enrollment, status, or Agent API key is persisted or emitted in logs/audit;
concurrent replay produces one pending application only.

### Task 4: Add Agent Enrollment JSON APIs

**Files:**

- Create: `server/modules/identity/agent_router.py`
- Modify: `server/modules/identity/router.py`
- Modify: `server/modules/identity/service.py`
- Modify: `server/modules/access/schemas.py`
- Modify: `server/app.py`
- Test: `tests/integration/test_agent_enrollment_api.py`
- Test: `tests/integration/test_openapi_response_models.py`

**Steps:**

1. Add failing API tests for submit, poll, approval observation, rejection, expired invitation, rate
   limiting, and denial of pending credentials on normal APIs.
2. Add dedicated dependencies that accept only `enroll_...` or `status_...` on enrollment routes.
3. Add response models that never serialize stored hashes.
4. Register the router and verify request IDs and stable error codes.
5. Regenerate and check OpenAPI.

**Exit criteria:** An Agent can apply and poll entirely through JSON, but cannot authenticate normal
APIs before approval.

### Task 5: Build The Maintainer Agent Console

**Files:**

- Create: `server/ui/routes/agents.py`
- Create: `server/ui/agents.py`
- Create: `server/templates/agents.html`
- Create: `server/templates/agent-invitation-created.html`
- Create: `server/static/js/modules/agents.js`
- Modify: `server/ui/navigation.py`
- Modify: `server/ui/formatting.py`
- Modify: `server/app.py`
- Test: `tests/integration/test_agent_admin_pages.py`
- Test: `tests/e2e/test_agent_enrollment_flow.py`

**Steps:**

1. Add failing tests proving contributors and Bearer-only callers cannot access Agent administration.
2. Build maintainer-only Session + CSRF routes that call shared identity services directly.
3. Render pending, active, suspended, rejected, expired, and empty states with complete template
   contexts.
4. Render the invitation prompt once after an idempotency-protected POST, set `Cache-Control:
   no-store`, prevent referrer/analytics leakage, and add an accessible local-only copy control.
5. Add approve/reject/suspend/resume/revoke confirmation flows without exposing raw secrets.
6. Verify keyboard navigation, focus restoration, narrow viewports, long Agent names, error states,
   POST refresh/replay behavior, and the absence of secret-bearing URLs or later retrieval.
7. Require approval confirmation using the public ID/fingerprint reported by the Agent, and add a
   race test proving a different submitted verifier cannot be approved with the expected fingerprint.

**Exit criteria:** A maintainer can complete the entire human side of enrollment without using an
Agent JSON API or handling a final Agent API key.

### Task 6: Make ServicePrincipal A First-Class Publisher

**Files:**

- Modify: `server/modules/access/authn.py`
- Modify: `server/modules/access/product_scope.py`
- Modify: `server/modules/access/credential_policy.py`
- Modify: `server/modules/identity/auth.py`
- Modify: `server/modules/authoring/api_support.py`
- Modify: `server/modules/authoring/router.py`
- Modify: `server/modules/release/router.py`
- Modify: `server/jobs.py`
- Modify: affected services that currently require `User`
- Test: `tests/integration/test_agent_service_principal_publish.py`
- Test: `tests/security/test_authorization.py`
- Test: `tests/integration/test_transaction_boundaries.py`

**Steps:**

1. Add a failing end-to-end service-Principal test covering create Skill, upload content, create
   version, create Release, materialize, and inspect ownership.
2. Admit `agent_token` as a Bearer Credential only when its ServicePrincipal is active.
3. Replace type-string authorization with a shared capability matrix and Agent policy checks.
   `agent_token` can invoke the server-side Agent publish operation but does not receive generic
   Exposure-admin or Review-decision capability.
4. Remove the Release requirement for `context.user`; compute maintainer bypass only for a real
   maintainer user and treat Agents as non-maintainer owners.
5. Enqueue Jobs with requesting Principal attribution.
6. Verify an Agent cannot read or mutate another Agent's private objects and cannot bypass quotas.
7. Define and test the capability matrix explicitly: Agent publish can create/own Skill content and
   trigger its server-side publication workflow, but cannot directly create/patch/activate/revoke
   arbitrary Exposures, decide Review Cases, issue tokens, or administer another namespace.
8. Make all Agent replacement Credentials inherit the enrollment policy and consume publish quota by
   ServicePrincipal, with atomic concurrent quota tests.

**Exit criteria:** An approved Agent publishes under its own namespace, every write is attributed to
its Principal and Credential, and no synthetic User is created.

### Task 7: Implement Public-By-Default Trusted Publisher Policy

**Files:**

- Create: `server/modules/release/agent_publish_router.py`
- Create: `server/modules/release/agent_publish_service.py`
- Modify: `server/modules/review/policy.py`
- Modify: `server/modules/exposure/service.py`
- Modify: `server/modules/exposure/router.py`
- Modify: `src/infinitas_skill/install/skill_validation.py`
- Modify: `src/infinitas_skill/registry/publish.py`
- Modify: `src/infinitas_skill/registry/cli.py`
- Test: `tests/integration/test_agent_public_publish_policy.py`
- Test: `tests/integration/test_private_registry_exposure_patch.py`
- Test: `tests/unit/registry/test_publish.py`

**Steps:**

1. Add failing tests proving an approved Agent with `auto_public_publish` gets an active public,
   listed, install-enabled Exposure after a ready compatible Release.
2. Add denial tests for suspended Agents, credentials without the policy capability, incompatible
   Releases, secret-bearing bundles, and exhausted quotas.
3. Pass a trusted server-derived publisher policy into Exposure evaluation; never accept an
   `auto_activate` flag from the client.
4. Make only the high-level Agent backup default to public. Keep the low-level generic `registry
   publish --visibility` choice explicit/private-first so unrelated automation does not become public
   as a side effect of Agent onboarding.
5. Preserve explicit private/grant publishing only when the Credential policy permits it.
6. Keep server-side canonical bundle validation as the final publication gate. Scan every regular
   file for the maintained secret/private-key signatures even when its path was explicitly allowed;
   scanner read/decode failures fail closed and cannot be overridden by client metadata.
7. Route Agent public backup through a server-side publish operation that receives only the skill
   payload/version and derives exposure audience, listing, install mode, review outcome, and
   `auto_public_publish` from the approved Credential policy. Do not give Agent credentials the
   generic Exposure-admin scope and do not trust a client `auto_activate` or visibility override.
8. Update authenticated audience authorization to accept active approved Agent Principals as well as
   user Principals, while preserving fail-closed suspension/revocation checks.
9. Test publish-intent idempotency and worker races: duplicate HTTP requests consume one quota unit;
   suspension/revocation before materialization prevents public Exposure; a policy change is applied
   before activation; successful retries reuse the same Release and Exposure.

**Exit criteria:** Agent approval can authorize automatic public backups without making public
modification anonymous or bypassing automated release safeguards.

### Task 8: Make Public Registry Reads Truly Anonymous

**Files:**

- Modify: `server/modules/registry/service.py`
- Modify: `server/settings.py`
- Modify: `src/infinitas_skill/install/http_registry.py`
- Modify: `src/infinitas_skill/registry/bootstrap_cli.py`
- Modify: `src/infinitas_skill/registry/local_ops.py`
- Modify: deployment/configuration templates
- Test: `tests/integration/test_public_registry_anonymous.py`
- Test: `tests/integration/test_registry_read_tokens.py`
- Test: `tests/unit/install/test_hosted_registry_source.py`

**Steps:**

1. Add failing anonymous tests for discovery, indexes, trust bootstrap, manifests, bundles,
   provenance, and signatures of public Releases.
2. Add tests proving anonymous requests cannot observe authenticated/grant/private entries or infer
   their artifact paths.
3. Remove `INFINITAS_REGISTRY_READ_TOKENS` and the global public-read gate.
4. Keep valid Agent/grant credentials additive: authenticated requests may see content allowed to
   their context; invalid supplied credentials return `401` rather than silently falling back.
5. Make Registry bootstrap tokens optional for public sources and update sync/update workflows.
6. Require HTTPS outside explicit loopback/test mode, persist the canonical Registry origin, reject
   cross-origin/scheme-downgrade redirects, and require an explicit re-trust operation when the
   installed trust/signing policy changes.

**Exit criteria:** A fresh unauthenticated Agent can discover, install, verify, and update every public
Skill, while non-public metadata and artifacts remain inaccessible.

### Task 9: Add Agent CLI Enrollment And Secure Profiles

**Files:**

- Create: `src/infinitas_skill/agent/`
- Modify: `src/infinitas_skill/cli/main.py`
- Modify: `src/infinitas_skill/registry/connection_cli.py`
- Test: `tests/unit/agent/test_profiles.py`
- Test: `tests/integration/test_agent_join_cli.py`

**Steps:**

1. Add failing tests for local status/API-key generation, stdin-only invitation input, `0700`
   directory/`0600` file modes, symlink rejection, atomic+fsync persistence, interrupted joins,
   pending/rejected/approved polling, lost-status-key behavior, profile selection, and redacted output.
2. Implement a structured profile file under a fixed platform configuration directory, never under
   the repository or Skill directory and never selected through an arbitrary filesystem path.
3. Generate and persist raw status/API keys before submission; send only verifiers.
4. On approval, verify the API key through `/access/me`, store non-secret server identity metadata,
   and bootstrap public trust material.
5. Ensure exceptions, JSON output, subprocess arguments, process listings, and logs never print any
   raw invitation, status, or final Agent key. Do not implement secret-bearing argv/environment
   options.
6. Preserve an existing valid profile on every failure path. A lost pending status key requires a new
   invitation; after approval, `/access/me` with the retained API key reconstructs non-secret state.

**Exit criteria:** Copying the generated prompt to an Agent is sufficient for it to apply, wait, and
configure an authenticated Registry profile without manual key transfer.

### Task 10: Add High-Level Skill Backup, Restore, Update, And Verify

**Files:**

- Create: `src/infinitas_skill/agent/skill_commands.py`
- Reuse/modify: `src/infinitas_skill/registry/publish.py`
- Reuse/modify: `src/infinitas_skill/install/`
- Modify: `src/infinitas_skill/cli/main.py`
- Test: `tests/integration/test_agent_skill_backup_restore.py`
- Test: `tests/security/test_agent_public_backup_safety.py`

**Steps:**

1. Add failing lifecycle tests: backup v1, bootstrap a public Registry profile in a fresh anonymous
   workspace, restore v1, backup v2, anonymous check-update/update, verify, and rollback. Also test
   explicit `--base-url` and the no-profile configuration error.
2. Add safety tests for `.env`, known token signatures, Authorization headers, private keys, runtime
   `data/`, credential/config files, shell histories, databases, symlinks, traversal,
   unreadable/scanner-failure input, oversize archives, path allow-list attempts, and version-content
   conflicts.
3. Implement thin Agent commands over the server-side Agent publish operation and existing
   install/verify services; do not duplicate packaging, extraction, integrity, Registry resolution,
   or rollback logic. The command must not call generic Exposure-admin endpoints with an elevated
   Agent token.
4. Require SemVer and preserve idempotency: same version + same digest succeeds; same version +
   different digest returns `409` and never overwrites.
5. Show included/excluded path inventory and public-visibility consequence before live backup.
6. Keep `--force` explicit for replacement and retain install-manifest rollback history.

**Exit criteria:** Public Skill program recovery works end to end without exposing or bundling runtime
data, and consumers cannot mutate the publisher's Registry object.

### Task 11: Add Agent Operations, Rotation, And Audit

**Files:**

- Modify: `server/modules/identity/agent_service.py`
- Modify: `server/modules/audit/read_model.py`
- Modify: `server/ui/agents.py`
- Modify: `server/templates/agents.html`
- Modify: `src/infinitas_skill/agent/`
- Test: `tests/integration/test_agent_credential_lifecycle.py`
- Test: `tests/integration/test_activity_api.py`

**Steps:**

1. Add tests for suspend/resume, permanent revoke, self-rotation with a locally generated replacement
   verifier, lost-key recovery through a maintainer-created recovery invitation, and last-used
   reporting.
2. Make rotation atomic: authenticate with the current key, install the new verifier, then revoke the
   old Credential in one transaction.
3. Make recovery a separate approval path: accept a proposed verifier through the one-use recovery
   invitation, approve it for the existing ServicePrincipal, revoke its lost Credentials atomically,
   and never create a second Principal or namespace.
4. Ensure suspension blocks all Agent credentials without destroying them; resume restores access.
5. Ensure revocation blocks future publication but does not silently delete or unpublish Releases.
6. Surface invitation, application, approval, publish, restore metadata access, rotation, recovery, suspension,
   and revocation events in Activity with request and credential attribution.
7. Test all one-use and terminal transitions on SQLite and the production database backend using
   concurrent requests; assert exactly one winner and deterministic `409`/terminal reads.

**Exit criteria:** Operators can disable or revoke an Agent predictably, rotate credentials without a
shared secret, and reconstruct the complete lifecycle from audit records.

### Task 12: Remove The Superseded Namespace-Token Surface

**Files:**

- Delete: `server/modules/access/namespace_tokens.py`
- Remove namespace-token service paths from `server/modules/access/token_service.py`
- Modify: `server/modules/access/router.py`
- Modify: `server/templates/settings.html`
- Modify/delete relevant logic in `server/static/js/modules/settings.js`
- Modify: `server/ui/routes/settings.py`
- Modify: tests and maintained references
- Regenerate: `openapi.json`, `server/static/.hashes.json`

**Steps:**

1. Change architecture tests to reject the old `/api/v1/namespace-tokens` routes and direct
   publisher-token form.
2. Remove the old API, UI, schemas, service paths, docs, environment guidance, and tests.
3. Keep object/release scoped delegation and Share Links because they serve distinct post-publication
   use cases.
4. Regenerate OpenAPI and frontend asset hashes.

**Exit criteria:** There is one Agent onboarding path, no administrator-identity publisher-token
shortcut, and no compatibility alias for the removed route or CLI behavior.

### Task 13: Complete Cross-Process And Browser Acceptance

**Files:**

- Rewrite: `tests/integration/test_agent_lifecycle_acceptance.py`
- Add/modify: `tests/e2e/test_agent_enrollment_flow.py`
- Modify: `tests/integration/test_python_distribution_assets.py` as required by CLI packaging
- Modify: docs/reference and OpenAPI contract tests

**Acceptance scenario:**

1. Start a clean API and worker from the sole initial migration.
2. Maintainer logs into the Web console and creates an Agent invitation.
3. A separate CLI process joins and reaches pending state.
4. Pending Agent attempts to publish and is denied.
5. Maintainer approves after inspecting identity metadata.
6. Agent verifies independent ServicePrincipal identity.
7. Agent backs up Skill v1 publicly; worker materializes and signs it.
8. An unauthenticated second workspace bootstraps the public Registry URL, discovers, restores, and
   verifies v1 without any reader or Agent credential.
9. Agent backs up v2; the unauthenticated workspace detects and installs the update.
10. A different approved Agent can update its own local copy but is denied every write to the first
    Agent's Skill. Cross-Agent authoring is not claimed or tested in this release.
11. Maintainer suspends the publisher; writes fail while public v1/v2 remain installable.
12. Maintainer revokes the publisher; credentials remain invalid and audit history remains complete.

**Exit criteria:** The scenario passes through real HTTP, subprocess CLI, worker, browser UI, database,
artifact storage, and signing paths.

## Verification Gates

Run focused tests after every task, then finish with all repository gates:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/infinitas_skill server
.venv/bin/pytest tests/unit tests/integration tests/security tests/performance
.venv/bin/pytest tests/e2e
.venv/bin/pytest tests/integration/test_alembic_metadata.py -q --override-ini=addopts=
.venv/bin/python scripts/generate-openapi.py --check
npm run build
git diff --check
```

Also verify:

- production modules remain at most 600 lines and functions at most 100 lines;
- `server/static/css/input.css` remains at most 1000 lines;
- top-level `scripts/` still contains exactly the four approved build/verification files;
- no raw `enroll_`, `status_`, or `agt_` value appears in database fixtures, logs, snapshots,
  OpenAPI examples, generated prompts after their one-time response, or test failure output;
- enrollment secrets never appear in argv, environment variables, URLs, referrers, analytics, audit
  payloads, or later retrieval responses;
- profile directories/files have `0700`/`0600` modes, reject symlink targets, and survive interrupted
  writes without losing a previously valid Agent key;
- anonymous public artifact URLs cannot be transformed to access private artifacts;
- public Registry clients reject non-test cleartext origins, cross-origin redirects, scheme downgrade,
  and unapproved signer/trust changes;
- import-time application construction does not initialize the database.

## Definition Of Done

- The Web console creates one-use Agent invitations and approves independent Agent identities.
- The copied prompt is sufficient for a supported Agent to apply and configure itself.
- The prompt uses non-echoed stdin for its one-use invitation; no supported command puts a secret in
  argv, environment variables, or a URL.
- The final Agent API key is generated and retained only by the Agent; the server stores a verifier.
- Pending, rejected, suspended, revoked, expired, and replay states fail closed.
- Approved Agents publish only within their own namespace and are independently auditable/revocable.
- Agent publication uses a server-derived, idempotent publish intent; no Agent token can directly
  administer Exposures or Review Cases, and quota/trust policy survives Credential rotation.
- Skill backups default to validated immutable public Releases.
- Public Skills are anonymously discoverable, restorable, verifiable, and locally updateable.
- A fresh anonymous workspace can bootstrap the Registry location explicitly; qualified Skill names
  do not implicitly select an untrusted Registry.
- Public consumers cannot modify publisher content.
- Enforced path policy, canonical content scanning, and fail-closed validation block runtime/business
  data and known secret forms from public Skill Releases; the UI still warns that automated scanning
  cannot prove arbitrary content is non-sensitive.
- Old namespace-token onboarding and global Registry reader-token behavior are deleted without aliases.
- ORM metadata, `0001_initial.py`, OpenAPI, docs, CLI reference, asset hashes, and tests agree.
