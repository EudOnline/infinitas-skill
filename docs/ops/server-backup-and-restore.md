---
audience: operators and release maintainers
owner: repository maintainers
source_of_truth: hosted backup and restore runbook
last_reviewed: 2026-07-21
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
  --label nightly \
  --json
```

Each backup directory contains:

- `repo.bundle` — a git bundle created from the clean server-owned checkout
- `server.db` — a copied SQLite database file
- `artifacts.tar.gz` — a tarball of the hosted artifact directory
- `manifest.json` — schema version, timestamp, label, git HEAD, source paths, and SHA-256 values for every restore input

The backup helper refuses dirty repo snapshots so operators do not accidentally capture an in-flight publish worktree.
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
  --label nightly \
  --json
```

Schedule the same command with a Coolify scheduled task or an external scheduler. The command
must run in a service that mounts the repo, data, artifact, and backup volumes.

The `infinitas-backups` volume protects against a bad application redeploy, but not against loss
of the Coolify server. Copy completed backup directories to independent object storage or a
different host and test that those exported copies can be retrieved.

## Recovery objectives

For the supported single-node SQLite deployment, use a one-hour database backup cadence and run
an additional backup immediately before each publish or image upgrade. This sets a target RPO of
one hour for ordinary writes and zero unplanned release-window loss after the pre-change backup.
The manual restore target is four hours (RTO), including volume recovery, ownership repair,
redeploy, readiness, worker heartbeat, and catalog checks.

These are operating targets, not guarantees. Test one restore rehearsal from an off-host copy at
least quarterly and after any deployment-layout change. PostgreSQL, multi-node, and managed
object-storage deployments require their own backup and recovery contract before production use.

If you install the generated `systemd` bundle from `uv run infinitas server render-systemd ...`, enable the matching backup timer so this command runs on a predictable schedule:

```bash
sudo systemctl enable --now infinitas-hosted-backup.timer
sudo systemctl list-timers infinitas-hosted-backup.timer
```

## Retention pruning

For a small single-node deployment, a reasonable starting retention policy is to keep the newest 7 hosted backup snapshots:

```bash
uv run infinitas server prune-backups \
  --backup-root /srv/infinitas/backups \
  --keep-last 7 \
  --json
```

The prune helper only deletes directories that:

- match the hosted backup timestamp naming convention
- contain `manifest.json`

Anything else under the backup root is left untouched and reported as `ignored`.

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
- copies and opens the SQLite DB backup
- extracts artifacts and confirms `ai-index.json` plus `catalog/`

Treat this as the safest first step before pointing any restored files at production service paths.

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
- PostgreSQL dumps and object-storage snapshots remain future automation work; v0.1 backup tooling supports only the single-node SQLite deployment shape
