# Hosted Registry Backup and Restore

This runbook covers the minimum backup set for a hosted `infinitas-skill` server.

## What to back up

- **Repo**: the writable source-of-truth checkout or a bare mirror of it
- **DB**: the hosted server database (`db`, `sqlite` file, or PostgreSQL dump)
- **Artifacts**: the hosted artifact directory that serves `ai-index.json`, `catalog/`, bundles, and provenance
- **Secrets metadata**: signing-key references, bootstrap user configuration, and service env manifests stored outside the repo

## Backup cadence

- Repo snapshots: before and after publish windows
- DB backups: frequent incremental or hourly snapshots
- Artifact backups: after each publish and daily full snapshots

## Automated backup command

For the current SQLite-first hosted deployment, create a point-in-time backup set with:

```bash
python scripts/backup-hosted-registry.py \
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
- `manifest.json` — backup metadata including timestamp, label, git HEAD, and source paths

The backup helper refuses dirty repo snapshots so operators do not accidentally capture an in-flight publish worktree.

## Restore sequence

1. Restore the repo snapshot to the server-owned checkout path
2. Restore the DB to the target database path or service
3. Restore the artifact directory in full
4. Reapply service environment and secret references
5. Run a hosted health check and inspect job queues
6. Verify the latest provenance with `python3 scripts/doctor-signing.py <skill> --provenance <path>`
7. Re-run `scripts/mirror-registry.sh --remote <mirror-remote> --dry-run` before re-enabling outward mirroring

## Recovery priorities

- Recover repo + db + artifacts together for a point-in-time consistent restore
- Do not restore GitHub back into the hosted source-of-truth repo
- If artifacts are missing but the repo is intact, rerun worker publish for the affected release after verifying tags and provenance
- PostgreSQL dumps and object-storage snapshots remain future automation work; phase 1 backup tooling currently targets the smallest SQLite deployment shape
