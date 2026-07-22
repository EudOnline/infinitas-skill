from __future__ import annotations

import sqlite3
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
            assert (backup_dir / "artifacts.tar.gz").exists()


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
