"""Create a hosted registry backup using the SQLite Online Backup API.

Usage:
    python scripts/backup-hosted.py --data-dir .deploy/data --repo-dir .deploy/repo \
        --artifact-dir .deploy/artifacts --output-dir .deploy/backups/manual

Creates a backup directory with:
    manifest.json        — backup metadata (timestamp, label, sizes)
    repo.bundle          — git bundle of the repository
    database.sqlite3     — consistent copy via SQLite Online Backup API
    artifacts.tar.gz     — compressed artifact directory
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_sqlite(source_db: Path, dest_db: Path) -> dict:
    """Copy a SQLite database safely using the Online Backup API.

    This produces a consistent snapshot even if the source database
    is being written to concurrently (unlike shutil.copy2).
    """
    dest_db.parent.mkdir(parents=True, exist_ok=True)
    if dest_db.exists():
        dest_db.unlink()

    src_conn = sqlite3.connect(str(source_db))
    dst_conn = sqlite3.connect(str(dest_db))

    try:
        src_conn.execute("BEGIN IMMEDIATE")
        src_conn.backup(dst_conn)
        dst_conn.execute("PRAGMA integrity_check")
    finally:
        dst_conn.close()
        src_conn.close()

    return {
        "sha256": _sha256_file(dest_db),
        "size_bytes": dest_db.stat().st_size,
    }


def backup_git_bundle(repo_dir: Path, bundle_path: Path) -> dict:
    """Create a git bundle of the repository."""
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    if bundle_path.exists():
        bundle_path.unlink()

    result = subprocess.run(
        ["git", "-C", str(repo_dir), "bundle", "create", str(bundle_path), "--all"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # git bundle create may fail if there are no commits; create empty bundle
        if "empty" not in result.stderr.lower():
            raise RuntimeError(f"git bundle create failed: {result.stderr.strip()}")

    return {
        "sha256": _sha256_file(bundle_path) if bundle_path.exists() else None,
        "size_bytes": bundle_path.stat().st_size if bundle_path.exists() else 0,
    }


def backup_artifacts(artifact_dir: Path, tar_path: Path) -> dict:
    """Create a compressed tarball of the artifact directory."""
    tar_path.parent.mkdir(parents=True, exist_ok=True)
    if tar_path.exists():
        tar_path.unlink()

    if not artifact_dir.exists():
        return {"sha256": None, "size_bytes": 0, "file_count": 0}

    file_count = 0
    with gzip.GzipFile(fileobj=tar_path.open("wb"), mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for path in sorted(artifact_dir.rglob("*")):
                if path.is_file():
                    rel = path.relative_to(artifact_dir)
                    info = tarfile.TarInfo(name=str(rel))
                    info.size = path.stat().st_size
                    info.mtime = 0
                    info.mode = 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    tar.addfile(info, open(path, "rb"))
                    file_count += 1

    return {
        "sha256": _sha256_file(tar_path),
        "size_bytes": tar_path.stat().st_size,
        "file_count": file_count,
    }


def create_backup(
    *,
    data_dir: Path,
    repo_dir: Path,
    artifact_dir: Path,
    output_dir: Path,
    label: str = "manual",
) -> Path:
    """Create a complete backup of the hosted registry."""
    timestamp = _utcnow_iso().replace(":", "-").replace("T", "_")
    backup_dir = output_dir / f"{label}-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. Find the SQLite database
    db_path = data_dir / "server.db"
    if not db_path.exists():
        raise FileNotFoundError(f"database not found: {db_path}")

    db_info = backup_sqlite(db_path, backup_dir / "database.sqlite3")

    # 2. Git bundle
    bundle_info = backup_git_bundle(repo_dir, backup_dir / "repo.bundle")

    # 3. Artifacts tarball
    artifact_info = backup_artifacts(artifact_dir, backup_dir / "artifacts.tar.gz")

    # 4. Manifest
    manifest = {
        "version": 1,
        "label": label,
        "created_at": _utcnow_iso(),
        "components": {
            "database": {"file": "database.sqlite3", **db_info},
            "repository": {"file": "repo.bundle", **bundle_info},
            "artifacts": {"file": "artifacts.tar.gz", **artifact_info},
        },
    }
    manifest_path = backup_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return backup_dir


def main():
    parser = argparse.ArgumentParser(description="Create a hosted registry backup")
    parser.add_argument(
        "--data-dir", required=True,
        help="Path to the data directory (contains server.db)",
    )
    parser.add_argument("--repo-dir", required=True, help="Path to the git repository")
    parser.add_argument("--artifact-dir", required=True, help="Path to the artifacts directory")
    parser.add_argument("--output-dir", required=True, help="Output directory for backups")
    parser.add_argument("--label", default="manual", help="Backup label (default: manual)")
    args = parser.parse_args()

    backup_path = create_backup(
        data_dir=Path(args.data_dir),
        repo_dir=Path(args.repo_dir),
        artifact_dir=Path(args.artifact_dir),
        output_dir=Path(args.output_dir),
        label=args.label,
    )
    print(f"backup created: {backup_path}")
    manifest = json.loads((backup_path / "manifest.json").read_text())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
