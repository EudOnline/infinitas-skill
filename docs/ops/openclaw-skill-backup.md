---
audience: operators and OpenClaw workspace maintainers
owner: repository maintainers
source_of_truth: OpenClaw snapshot and DataHub backup runbook
last_reviewed: 2026-07-29
status: maintained
---

# OpenClaw Skill Backup And Restore

Registry Releases version the skill program and its immutable distribution files. They do not
automatically include data stored outside the skill directory. A workspace skill such as
`teacher-work-datahub` normally has this layout:

```text
~/.agents/skills/teacher-work-datahub/   # code, SKILL.md, parsers, references
~/.agents/data/teacher-work-datahub/     # raw, catalog, curated, indexes, outputs
```

Use a private Registry Release for the first tree and an encrypted OpenClaw snapshot for the
second tree. Do not publish workspace data as a public skill version.

If a legacy skill still contains runtime data inside its own directory, add a root-level
`.infinitasignore` before publishing. The file accepts one relative file or directory prefix per
line (blank lines and `#` comments are ignored):

```text
# Legacy runtime data now backed up from ~/.agents/data/<skill>
data/
```

`registry publish --dry-run` reports `excluded_paths` and the complete `included_paths` inventory;
inspect both before a live write. Hosted publication also rejects runtime `data/`, databases,
credential/cookie exports, and private-key filenames unless a legitimate static fixture has an
explicit metadata allowlist. Move durable runtime truth to `~/.agents/data/<skill>` rather than
relying on exclusions as the long-term data architecture.

## Create A Snapshot

An age recipient is public encryption input. Keep the matching age identity outside the workspace
and outside the backup destination:

```bash
infinitas openclaw skill backup \
  ~/.agents/skills/teacher-work-datahub \
  --data-dir ~/.agents/data/teacher-work-datahub \
  --out /srv/backups/teacher-work-datahub-2026-07-24.tar.gz.age \
  --age-recipient age1... \
  --json
```

The snapshot contains a SHA-256 manifest for every regular file. It rejects symlinks and special
files, excludes build/test caches from the skill tree and non-template `.env` files from both the
skill and data trees, detects concurrent source changes, verifies the completed plaintext archive,
returns archive/manifest SHA-256 values, writes output mode `0600`, and
requires encryption whenever `--data-dir` is present. `--allow-plaintext-data` is reserved for
an explicitly isolated local rehearsal.

After restricted WebDAV upload and download verification, register only its recovery metadata:

```bash
infinitas registry data-snapshots register <skill-id> \
  --skill-version-id <version-id> \
  --file /srv/backups/teacher-work-datahub-2026-07-24.tar.gz.age \
  --object-uri openlist://newins/infinitas-skill-backups/agent-data-snapshots/teacher-work-datahub/2026-07-24.tar.gz.age \
  --manifest-digest sha256:<digest-from-backup-output> \
  --parent-snapshot-id <previous-snapshot-id>
```

The production OpenList root exposes storage mounts rather than a writable virtual filesystem.
Create snapshot directories below the existing `/newins` mount and restrict the snapshot user
to `/newins/infinitas-skill-backups/agent-data-snapshots`; a root-level directory without a
storage mount will fail even when authentication succeeds.

OpenList maps this user's base path to the WebDAV root. Configure the client with
`https://openlist.infinitas.fun/dav` and address objects relative to that root; do not prefix
requests with `/newins` or the full base path.

For long-lived automation, use a non-admin OpenList user with permission value `776`: content
write, WebDAV read, and WebDAV write. This intentionally omits delete permission. If an ancestor
OpenList Meta restricts `read_users` or `write_users`, create a more-specific Meta on
`/newins/infinitas-skill-backups/agent-data-snapshots`, include the administrator and snapshot
user IDs, and enable both subdirectory flags. A base path alone does not override an ancestor Meta
ACL. Verify the account by uploading an `.age` object, downloading it, comparing SHA-256, and
confirming that deletion is denied.

The Registry stores metadata and lineage only. It does not receive the snapshot bytes, WebDAV
password, or age identity.

Encrypted output must use the `.age` suffix; plaintext rehearsal output must not use it. The
skill and data source trees, the snapshot output, and restore targets must be separate paths.
This prevents a backup from capturing itself or a restore from replacing one payload inside the
other.

## Verify And Restore

Always verify before replacing a live workspace:

```bash
infinitas openclaw skill restore \
  /srv/backups/teacher-work-datahub-2026-07-24.tar.gz.age \
  --age-identity /srv/keys/teacher-work-datahub.agekey \
  --verify-only --json
```

Restore into a new workspace first. `--force` is required to replace existing targets and the
replacement is staged and swapped atomically per target:

```bash
infinitas openclaw skill restore \
  /srv/backups/teacher-work-datahub-2026-07-24.tar.gz.age \
  --age-identity /srv/keys/teacher-work-datahub.agekey \
  --skill-dir /srv/rehearsal/.agents/skills/teacher-work-datahub \
  --data-dir /srv/rehearsal/.agents/data/teacher-work-datahub \
  --json

TEACHER_WORK_DATAHUB_ROOT=/srv/rehearsal/.agents \
  python3 /srv/rehearsal/.agents/skills/teacher-work-datahub/scripts/registry/bootstrap_report.py --json
TEACHER_WORK_DATAHUB_ROOT=/srv/rehearsal/.agents \
  python3 /srv/rehearsal/.agents/skills/teacher-work-datahub/scripts/query/healthcheck_datahub.py --mode core
```

For DataHub verification, compare `raw/`, `catalog/`, and `curated/` byte-for-byte. Treat
`outputs/` as regenerable evidence: healthchecks rewrite timestamps and report files by design.

## Data Policy

- `raw/`: immutable source records; highest restore priority.
- `catalog/`, `curated/`, and lineage/index files: current business truth; restore and hash-check.
- `outputs/`: generated delivery and health reports; restore optionally, then regenerate.
- API tokens, OCR keys, Feishu credentials, age identities, and non-template `.env` files: never
  put them in a skill Release or snapshot; restore them from a secret manager or host credential
  store. Keep only `.env.example`, `.env.sample`, or `.env.template` files with empty values.
- A skill Release is not a database backup. Keep independent encrypted snapshots with at least
  one off-host copy and periodically perform a restore rehearsal.

An OpenList-mounted Google Drive is suitable for the off-host copy only after the snapshot is
encrypted locally. Upload the `.tar.gz.age` object through a restricted WebDAV user, then download
it and compare SHA-256 before recording completion. Never upload the age identity, plaintext
workspace data, `.env` files, or a broad OpenList administrator credential. Keep OpenClaw snapshot
retention separate from hosted-registry receipts because their recovery units and data owners are
different.

For `teacher-work-datahub`, the current release position remains private/incubating and
workspace-scoped. It is not a zero-configuration public skill.
