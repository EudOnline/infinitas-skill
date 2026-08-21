---
audience: Agent authors, administrators, operators
owner: repository maintainers
source_of_truth: ChangeSet and encrypted data snapshot workflow
last_reviewed: 2026-08-21
status: maintained
---

# Agent Collaboration And Private Skill Data

The Registry separates three recovery units:

| Unit | Authority | Stored by Registry | Mutation model |
|---|---|---|---|
| Skill source candidate | Agent workspace | validated pending bundle | one-use until promoted |
| Skill version and Release | Registry | immutable bundle, manifest, provenance | append only |
| Skill runtime/business data | Agent data directory + encrypted object store | metadata only | independent snapshots |

The Web UI remains read-only for skill authoring. Agents use Bearer credentials and the JSON API
or CLI. Every write audit event records the principal, credential ID, `issued_for`, and request ID
when those values are available.

## Agent Enrollment And Public Program Backup

An administrator creates an invitation from `/agents`. The HTML form uses Session Cookie + CSRF and
a server-generated one-use nonce; the resulting `enroll_...` secret is shown once in a response that
must not be cached. The Agent submits its locally generated credential/status verifiers through the
JSON enrollment API, then polls with the separate `status_...` credential until an administrator
approves or rejects it. Submission and polling have separate persistent rate limits, and approval
creates an independently revocable service Principal rather than delegating an administrator user.

An approved Agent backs up program files through the Agent publish orchestration. Its credential
needs `agent:publish` to create or reuse an intent and `release:read` to poll materialization. The
first publish request returns `202`, an idempotent retry returns `200`, and daily quota exhaustion
returns `429` with a retry interval. The CLI reports success only after the immutable Release is
`ready` and the owner-scoped intent is `activated`; a `suppressed` intent is a failed public backup
and includes the server reason. Public activation is server-derived and never gives the Agent
generic Exposure administration.

This public backup contains only Skill program files. It is not a backup of runtime or business
data. Runtime state follows the encrypted snapshot workflow below and is never exposed through the
public catalog or public artifact routes.

## Multiple Agents On One Skill

Give each Agent a separate namespace or object publisher Token. Do not share one bearer secret:
separate credentials provide revocation, quota, and audit attribution.

Each Agent prepares and uploads a candidate bundle, then creates a ChangeSet against the same
current base version:

```bash
export INFINITAS_REGISTRY_API_BASE_URL=https://skills.infinitas.fun
export INFINITAS_REGISTRY_API_TOKEN=<agent-specific-publisher-token>

infinitas registry skills upload-content <skill-id> candidate.tar.gz
infinitas registry changesets create <skill-id> \
  --base-version-id <current-version-id> \
  --content-id <content-id> \
  --version 1.2.0
infinitas registry changesets submit <skill-id> <change-set-id>
```

The accepting Agent must supply the digest it reviewed:

```bash
infinitas registry changesets accept <skill-id> <change-set-id> \
  --expected-latest-digest sha256:<current-content-digest>
```

Acceptance atomically compares the expected digest, consumes the candidate, creates an immutable
version, and supersedes other open/submitted ChangeSets based on the old version. A concurrent or
stale acceptance returns `409`; it never overwrites a version. The losing Agent fetches the new
latest version, merges or regenerates its candidate in its own Git/worktree, uploads new content,
and creates a new ChangeSet. The Registry deliberately does not merge source files.

Reject a candidate explicitly when it should not be rebased:

```bash
infinitas registry changesets reject <skill-id> <change-set-id>
```

## Hosted Publish Data Policy

`registry publish --dry-run` returns `included_paths`, sizes, generated files, and exclusions.
Review the complete inventory before a live write.

Hosted publication rejects these paths by default:

- `data/` runtime trees;
- SQLite/database files;
- credential, cookie, auth, and secret export filenames;
- private key and certificate-container files;
- non-template `.env` files and known token/private-key content signatures.

Use `.infinitasignore` to remove runtime data. A legitimate static fixture can be allowed only by
an exact `_meta.json` declaration:

```json
{
  "security": {
    "publish_allow_paths": ["fixtures/empty.sqlite"]
  }
}
```

The allowlist is a security exception, not a place to approve real credentials or workspace data.

## Encrypted Data Snapshots

Keep business data under a separate data directory. The snapshot command excludes non-template
`.env` files from both source trees, detects concurrent file changes, verifies its completed
plaintext archive before encryption, and returns the archive and manifest digests:

```bash
infinitas openclaw skill backup ~/.agents/skills/<skill> \
  --data-dir ~/.agents/data/<skill> \
  --out /srv/backups/<skill>-2026-07-29.tar.gz.age \
  --age-recipient age1... --json
```

Upload only the `.age` file through a restricted OpenList WebDAV account. After downloading and
comparing its SHA-256, register recovery metadata:

```bash
infinitas registry data-snapshots register <skill-id> \
  --skill-version-id <version-id> \
  --file /srv/backups/<skill>-2026-07-29.tar.gz.age \
  --object-uri openlist://newins/infinitas-skill-backups/agent-data-snapshots/<skill>/<snapshot>.tar.gz.age \
  --manifest-digest sha256:<manifest-digest> \
  --parent-snapshot-id <previous-snapshot-id>
```

The first URI component must name a real OpenList storage mount. In the production layout that is
`/newins`; a root-level virtual path such as `/skill-data-snapshots` has no backing storage and
cannot be used for WebDAV uploads. Give the Agent snapshot account a base path limited to
`/newins/infinitas-skill-backups/agent-data-snapshots`. Use OpenList permission value `776`
(content write plus WebDAV read/write) without delete permission. When a parent OpenList Meta has
an explicit user ACL, add a more-specific Meta at the snapshot path for the administrator and
snapshot user; the user's base path does not bypass Meta ACLs.

The Registry stores the encrypted object URI, ciphertext digest/size, manifest digest, schema
version, parent link, related skill version, and creator attribution. It does not proxy the file,
store plaintext data, store WebDAV credentials, or store an age identity.

Recovery order is: query snapshot metadata, download with an independently supplied restricted
credential, verify the ciphertext digest, decrypt/verify with the offline age identity, restore to
a new directory, run the skill's business healthcheck, then swap into service.

## Data Classification

| Class | Examples | Destination |
|---|---|---|
| Program | `SKILL.md`, scripts, schemas, empty templates | immutable private/public Release |
| Durable business truth | raw inputs, catalogs, curated records, SQLite runtime state | encrypted data snapshot |
| Regenerable output | reports, caches, derived indexes | snapshot only when recovery value warrants it |
| Secret | API tokens, cookies, OAuth exports, age identity, `.env` | secret manager/host credential store only |

OpenList is an immutable off-host copy, not a shared live filesystem. Concurrent writers need the
skill application's own transaction/locking model; snapshot creation fails if files change during
collection rather than claiming a consistent backup.
