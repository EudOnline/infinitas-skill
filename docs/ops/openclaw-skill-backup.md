---
audience: operators and OpenClaw workspace maintainers
owner: repository maintainers
source_of_truth: OpenClaw snapshot and DataHub backup runbook
last_reviewed: 2026-07-24
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

The snapshot contains a SHA-256 manifest for every regular file. It rejects symlinks and
special files, excludes build/test caches and non-template `.env` files from the skill tree,
writes output mode `0600`, and
requires encryption whenever `--data-dir` is present. `--allow-plaintext-data` is reserved for
an explicitly isolated local rehearsal.

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

For `teacher-work-datahub`, the current release position remains private/incubating and
workspace-scoped. It is not a zero-configuration public skill.
