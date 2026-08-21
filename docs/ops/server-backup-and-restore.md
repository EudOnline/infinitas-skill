---
audience: operators and release maintainers
owner: repository maintainers
source_of_truth: hosted backup and restore runbook
last_reviewed: 2026-07-28
status: maintained
---

# Hosted Registry Backup and Restore

This runbook covers the minimum backup set for a hosted `infinitas-skill` server.

For volume names, terminals, deployment upgrades, and rollback on Coolify, also read the
[Coolify deployment runbook](coolify-deployment.md).

## What to back up

- **Repo**: the writable source-of-truth checkout or a bare mirror of it
- **DB**: the hosted SQLite database file
- **Artifacts**: the hosted artifact directory that serves `ai-index.json`, `catalog/`, bundles, and provenance
- **Secrets metadata**: signing-key references, bootstrap user configuration, and service env manifests stored outside the repo

## Backup cadence

- Repo snapshots: before and after publish windows
- DB backups: frequent incremental or hourly snapshots
- Artifact backups: after each publish and daily full snapshots

## Automated backup command

For the current SQLite-first hosted deployment, create a point-in-time backup set with:

```bash
uv run infinitas server backup \
  --repo-path /srv/infinitas/repo \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --artifact-path /srv/infinitas/artifacts \
  --output-dir /srv/infinitas/backups \
  --lock-path /srv/infinitas/data/repo.lock \
  --label nightly \
  --json
```

Each backup directory contains:

- `repo.bundle` — a git bundle created from the clean server-owned checkout
- `server.db` — a transactionally consistent SQLite snapshot created with SQLite's online backup API
- `artifacts.tar.gz` — a tarball of the hosted artifact directory
- `manifest.json` — schema version, timestamp, label, git HEAD, source paths, and SHA-256 values for every restore input

Snapshot directories are created with mode `0700` and their files with mode `0600` because the
SQLite snapshot and manifest may contain sensitive operational state.

The backup helper refuses dirty repo snapshots so operators do not accidentally capture an in-flight publish worktree.
It publishes a snapshot directory only after every file and the manifest are complete. The shared
`repo.lock` serializes the snapshot with worker materialization and cleanup, while a separate
backup lock rejects overlapping backup commands.
It runs `PRAGMA integrity_check` against the completed SQLite snapshot before accepting the backup.
The restore rehearsal refuses backup sets without valid SHA-256 values, so a backup is not considered
recoverable merely because its files still exist.

### Run a backup on Coolify

Open the terminal for the `app` service and run:

```bash
export PYTHONPATH=/opt/infinitas/bundle/src:/opt/infinitas/bundle
python3 -m infinitas_skill.cli.main server backup \
  --repo-path /srv/infinitas/repo \
  --database-url sqlite:////srv/infinitas/data/server.db \
  --artifact-path /srv/infinitas/artifacts \
  --output-dir /srv/infinitas/backups \
  --lock-path /srv/infinitas/data/repo.lock \
  --label nightly \
  --json
```

Schedule the same command with a Coolify scheduled task or an external scheduler. The command
must run in a service that mounts the repo, data, artifact, and backup volumes.

The `infinitas-backups` volume protects against a bad application redeploy, but not against loss
of the Coolify server. Use the encrypted export below for server-loss recovery.

## Encrypted offsite export through OpenList

Use OpenList only as a replaceable WebDAV gateway. The durable offsite medium is the storage
mounted below `/newins`. In OpenList, create a dedicated non-admin user with:

- base path `/newins/infinitas-skill-backups`
- only WebDAV read and WebDAV write permissions
- a unique random password used with Basic Auth

OpenList exposes that base path as `/dav/` to this user. Keep the exporter URL at
`https://openlist.infinitas.fun/dav` and use a relative remote prefix; do not append `/newins` or
the base path to the WebDAV request path.

Do not use an administrator API Token as a Basic password. Generate an age identity on an offline
recovery host, store the identity outside Coolify and Google Drive, and put only its public
recipient in Coolify.

Run the exporter in the `backup-exporter` container:

```bash
infinitas server export-backups \
  --backup-root /srv/infinitas/backups \
  --staging-dir /srv/infinitas/backup-staging \
  --receipt-root /srv/infinitas/backup-receipts \
  --webdav-url "$INFINITAS_BACKUP_WEBDAV_URL" \
  --remote-prefix "$INFINITAS_BACKUP_REMOTE_PREFIX" \
  --age-recipient "$INFINITAS_BACKUP_AGE_RECIPIENT" \
  --auth-mode basic \
  --json
```

The password is read only from `INFINITAS_BACKUP_WEBDAV_PASSWORD`; there is no plaintext secret
argument. Before upload, the command verifies all manifest hashes, the Git bundle, and SQLite
integrity. It uploads only a `.tar.gz.age` archive, downloads it again to verify the encrypted
SHA-256, then writes the remote and local receipt. Production receipts use a separate volume so
the exporter keeps the snapshot volume read-only. An upload without a matching receipt is never
overwritten automatically. A matching remote receipt can reconstruct local state after an
interrupted run.

Monitor backup freshness independently from application readiness:

```bash
infinitas server inspect-backup-state \
  --backup-root /srv/infinitas/backups \
  --receipt-root /srv/infinitas/backup-receipts \
  --max-local-age-hours 2 \
  --max-offsite-age-hours 3 \
  --json
```

OpenList or Google Drive downtime must alert, but must not make the registry API unready.

## Recovery objectives

For the supported single-node SQLite deployment, use a one-hour database backup cadence and run
an additional backup immediately before each publish or image upgrade. This sets a target RPO of
one hour for ordinary writes and zero unplanned release-window loss after the pre-change backup.
The manual restore target is four hours (RTO), including volume recovery, ownership repair,
redeploy, readiness, worker heartbeat, and catalog checks.

These are operating targets, not guarantees. Test one restore rehearsal from an off-host copy at
least quarterly and after any deployment-layout change. Other database engines, multi-node
deployments, and managed object storage are outside this product's backup and recovery contract.

If you install the generated `systemd` bundle from `uv run infinitas server render-systemd ...`, enable the matching backup timer so this command runs on a predictable schedule:

```bash
sudo systemctl enable --now infinitas-hosted-backup.timer
sudo systemctl list-timers infinitas-hosted-backup.timer
```

## Retention pruning

For a small single-node deployment, keep the newest 48 hourly hosted backup snapshots:

```bash
uv run infinitas server prune-backups \
  --backup-root /srv/infinitas/backups \
  --keep-last 48 \
  --require-offsite-receipt \
  --receipt-root /srv/infinitas/backup-receipts \
  --json
```

The prune helper only deletes directories that:

- match the hosted backup timestamp naming convention
- contain `manifest.json`

Anything else under the backup root is left untouched and reported as `ignored`. With
`--require-offsite-receipt`, snapshots without a completed offsite receipt are protected even if
they are older than the local retention window. Do not automate remote deletion during the first
30 production days; define and test a separate GFS policy after the first successful drill.

If you install the generated `systemd` bundle, enable the prune timer so retention cleanup stays aligned with scheduled backups:

```bash
sudo systemctl enable --now infinitas-hosted-prune.timer
sudo systemctl list-timers infinitas-hosted-prune.timer
```

## Restore rehearsal

Before restoring onto a real server path, rehearse the backup into a staging directory:

```bash
uv run infinitas server restore-rehearsal \
  --backup-dir /srv/infinitas/backups/20260314T010000Z-nightly \
  --output-dir /tmp/infinitas-restore-drill \
  --json
```

This drill:

- validates `manifest.json`
- verifies SHA-256 values before reading the git bundle, database, or artifact archive
- verifies the git bundle
- clones the repo bundle into a staging checkout
- copies the SQLite DB backup and requires `PRAGMA integrity_check` to return `ok`
- extracts artifacts and confirms `ai-index.json` plus `catalog/`

Treat this as the safest first step before pointing any restored files at production service paths.

For the required offsite drill, run this on the secured recovery host that holds the age identity.
Copy the snapshot's `manifest.json` into a same-named local directory and its receipt into a
separate local receipt directory, provide the dedicated WebDAV credentials through environment
variables, and run:

```bash
infinitas server verify-offsite-backup \
  --backup-dir ./20260728T010000Z-scheduled \
  --receipt-root ./receipts \
  --output-dir ./restore-rehearsal \
  --webdav-url https://openlist.infinitas.fun/dav \
  --auth-mode basic \
  --age-identity /secure/offline/infinitas-backup.agekey \
  --json
```

The command downloads the encrypted archive, verifies its receipt, decrypts into a private
temporary directory, rejects unsafe archive members, validates the inner backup again, and runs
the same isolated repo/SQLite/artifact restore rehearsal. Run this quarterly and after any change
to the image, volume layout, OpenList storage, WebDAV account, or age tooling.

## Restore sequence

1. Stop the API app and worker so no writes occur during restore.
2. Restore the repo snapshot to the server-owned checkout path.
3. Restore the SQLite DB to the target database path.
4. Restore the artifact directory in full.
5. Reapply service environment and secret references.
6. Start one app and one worker.
7. Run readiness, worker-heartbeat, and hosted state checks.
8. Verify the latest provenance with `uv run infinitas release doctor-signing <skill> --provenance <path>`.
9. Re-run `uv run infinitas registry sources mirror --remote <mirror-remote> --dry-run` before re-enabling outward mirroring.

Coolify does not provide an application-level restore endpoint for this project. Restore is an
operator procedure: stop the services, restore the named-volume contents, verify ownership is
`1000:1000`, then redeploy and validate. When deleting or recreating a resource, preserve the
persistent volumes.

## Recovery priorities

- Recover repo + db + artifacts together for a point-in-time consistent restore
- Back up immediately before every image upgrade and retain the previous immutable image tag
- Do not restore GitHub back into the hosted source-of-truth repo
- If artifacts are missing but the repo is intact, rerun worker publish for the affected release after verifying tags and provenance
- Backup tooling intentionally supports only the single-node SQLite and filesystem deployment shape
