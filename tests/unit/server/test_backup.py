from __future__ import annotations

import sqlite3
import stat
import subprocess
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from src.infinitas_skill.server.backup import (
    archive_artifacts,
    build_backup_checksums,
    build_prune_summary,
    classify_backup_entries,
    copy_sqlite_db,
    create_backup_dir,
    run_server_backup,
    sanitize_label,
)


class TestSanitizeLabel:
    def test_basic(self):
        assert sanitize_label("hello world") == "hello-world"

    def test_special_chars(self):
        assert sanitize_label("hello@world#test") == "hello-world-test"

    def test_leading_trailing(self):
        assert sanitize_label("---hello---") == "hello"

    def test_empty(self):
        assert sanitize_label("") == ""

    def test_whitespace_only(self):
        assert sanitize_label("   ") == ""


class TestCreateBackupDir:
    def test_creates_directory(self):
        with TemporaryDirectory() as td:
            backup_dir, timestamp = create_backup_dir(td, "test")
            assert backup_dir.exists()
            assert backup_dir.is_dir()
            assert stat.S_IMODE(backup_dir.stat().st_mode) == 0o700
            assert len(timestamp) == 16  # YYYYMMDDTHHMMSSZ

    def test_no_label(self):
        with TemporaryDirectory() as td:
            backup_dir, timestamp = create_backup_dir(td, "")
            assert backup_dir.name == timestamp


class TestCopySqliteDb:
    def test_creates_consistent_online_backup(self):
        with TemporaryDirectory() as td:
            db_path = Path(td) / "test.db"
            source = sqlite3.connect(db_path)
            source.execute("PRAGMA journal_mode=WAL")
            source.execute("CREATE TABLE entries (value TEXT NOT NULL)")
            source.execute("INSERT INTO entries VALUES ('committed')")
            source.commit()
            backup_dir = Path(td) / "backup"
            backup_dir.mkdir()
            try:
                result = copy_sqlite_db(db_path, backup_dir)
            finally:
                source.close()

            backup_path = backup_dir / "test.db"
            with closing(sqlite3.connect(backup_path)) as backup:
                rows = backup.execute("SELECT value FROM entries").fetchall()
                integrity = backup.execute("PRAGMA integrity_check").fetchall()

            assert result == "test.db"
            assert rows == [("committed",)]
            assert integrity == [("ok",)]
            assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600


class TestArchiveArtifacts:
    def test_creates_archive(self):
        with TemporaryDirectory() as td:
            artifact_path = Path(td) / "artifacts"
            artifact_path.mkdir()
            (artifact_path / "file.txt").write_text("content", encoding="utf-8")
            backup_dir = Path(td) / "backup"
            backup_dir.mkdir()
            result = archive_artifacts(artifact_path, backup_dir)
            assert result == "artifacts.tar.gz"
            archive_path = backup_dir / "artifacts.tar.gz"
            assert archive_path.exists()
            assert stat.S_IMODE(archive_path.stat().st_mode) == 0o600


def test_run_server_backup_secures_every_snapshot_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    (repo / "README.md").write_text("backup fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True)
    database = tmp_path / "server.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE entries (value TEXT NOT NULL)")
        connection.commit()
    artifacts = tmp_path / "artifacts"
    (artifacts / "catalog").mkdir(parents=True)
    (artifacts / "ai-index.json").write_text("{}\n", encoding="utf-8")
    output = tmp_path / "backups"

    assert (
        run_server_backup(
            repo_path=str(repo),
            database_url=f"sqlite:///{database}",
            artifact_path=str(artifacts),
            output_dir=str(output),
            label="permissions",
            as_json=True,
        )
        == 0
    )

    snapshot = next(output.iterdir())
    assert stat.S_IMODE(snapshot.stat().st_mode) == 0o700
    assert {path.name for path in snapshot.iterdir()} == {
        "repo.bundle",
        "server.db",
        "artifacts.tar.gz",
        "manifest.json",
    }
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in snapshot.iterdir())


class TestBuildBackupChecksums:
    def test_hashes_each_named_backup_file(self):
        with TemporaryDirectory() as td:
            backup_dir = Path(td)
            (backup_dir / "repo.bundle").write_bytes(b"repo")
            (backup_dir / "server.db").write_bytes(b"database")

            checksums = build_backup_checksums(backup_dir, ["repo.bundle", "server.db"])

            assert set(checksums) == {"repo.bundle", "server.db"}
            assert all(len(checksum) == 64 for checksum in checksums.values())


class TestClassifyBackupEntries:
    def test_classifies_correctly(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            valid = root / "20240101T000000Z-test"
            valid.mkdir()
            (valid / "manifest.json").write_text("{}", encoding="utf-8")
            invalid = root / "not-a-backup"
            invalid.mkdir()
            ignored_file = root / "random.txt"
            ignored_file.write_text("hi", encoding="utf-8")
            eligible, ignored = classify_backup_entries(root)
            assert len(eligible) == 1
            assert eligible[0].name == "20240101T000000Z-test"
            assert len(ignored) == 2


class TestBuildPruneSummary:
    def test_keeps_recent(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            for name in ["20240103T000000Z", "20240102T000000Z", "20240101T000000Z"]:
                d = root / name
                d.mkdir()
                (d / "manifest.json").write_text("{}", encoding="utf-8")
            summary = build_prune_summary(root, 2)
            assert len(summary["kept"]) == 2
            assert len(summary["deleted"]) == 1
            assert "20240101T000000Z" in summary["deleted"][0]
