from __future__ import annotations

import json
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

import httpx

from infinitas_skill.server.backup import classify_backup_entries, run_server_backup
from infinitas_skill.server.backup_export import (
    RECEIPT_NAME,
    WebDAVClient,
    run_server_export_backups,
    run_server_inspect_backup_state,
    run_server_verify_offsite_backup,
)


class MemoryWebDAV:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.authorization_headers: set[str] = set()

    def handle(self, request: httpx.Request) -> httpx.Response:
        authorization = request.headers.get("authorization")
        if authorization:
            self.authorization_headers.add(authorization)
        path = request.url.path
        if request.method == "MKCOL":
            return httpx.Response(201)
        if request.method == "HEAD":
            return httpx.Response(200 if path in self.files else 404)
        if request.method == "PUT":
            if request.headers.get("if-none-match") == "*" and path in self.files:
                return httpx.Response(412)
            self.files[path] = request.read()
            return httpx.Response(201)
        if request.method == "GET":
            payload = self.files.get(path)
            if payload is not None:
                return httpx.Response(200, content=payload)
            return httpx.Response(404)
        return httpx.Response(405)


def _create_snapshot(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    (repo / "README.md").write_text("offsite fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "fixture"], check=True)
    database = tmp_path / "server.db"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("CREATE TABLE entries (value TEXT NOT NULL)")
        connection.execute("INSERT INTO entries VALUES ('offsite')")
        connection.commit()
    artifacts = tmp_path / "artifacts"
    (artifacts / "catalog").mkdir(parents=True)
    (artifacts / "ai-index.json").write_text("{}\n", encoding="utf-8")
    root = tmp_path / "backups"
    run_server_backup(
        repo_path=str(repo),
        database_url=f"sqlite:///{database}",
        artifact_path=str(artifacts),
        output_dir=str(root),
        label="offsite",
        as_json=True,
    )
    snapshots, _ignored = classify_backup_entries(root)
    return root, snapshots[0]


def _age_keypair(tmp_path: Path) -> tuple[Path, str]:
    identity = tmp_path / "age-identity.txt"
    subprocess.run(["age-keygen", "--output", str(identity)], check=True, capture_output=True)
    result = subprocess.run(
        ["age-keygen", "--y", str(identity)], check=True, text=True, capture_output=True
    )
    return identity, result.stdout.strip()


def _webdav_client(backend: MemoryWebDAV) -> WebDAVClient:
    return WebDAVClient(
        base_url="https://openlist.example/dav",
        auth_mode="basic",
        username="backup-user",
        secret="test-password",
        transport=httpx.MockTransport(backend.handle),
    )


def test_export_roundtrip_and_isolated_restore(tmp_path: Path, capsys) -> None:
    backup_root, snapshot = _create_snapshot(tmp_path)
    capsys.readouterr()
    identity, recipient = _age_keypair(tmp_path)
    backend = MemoryWebDAV()
    client = _webdav_client(backend)
    receipt_root = tmp_path / "receipts"

    assert (
        run_server_export_backups(
            backup_root=str(backup_root),
            staging_dir=str(tmp_path / "staging"),
            webdav_url="unused",
            remote_prefix="skills.infinitas.fun",
            receipt_root=str(receipt_root),
            age_recipient=recipient,
            auth_mode="basic",
            user_env="UNUSED_USER",
            secret_env="UNUSED_SECRET",
            as_json=True,
            client=client,
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    local_receipt = receipt_root / f"{snapshot.name}.json"
    receipt = json.loads(local_receipt.read_text(encoding="utf-8"))
    assert summary["exports"][0]["status"] == "exported"
    assert receipt["remote_archive_path"].endswith(".tar.gz.age")
    assert any(path.endswith(".receipt.json") for path in backend.files)
    assert not any(path.endswith(".tar.gz") for path in backend.files)
    assert backend.authorization_headers == {"Basic YmFja3VwLXVzZXI6dGVzdC1wYXNzd29yZA=="}

    restore_output = tmp_path / "restore"
    assert (
        run_server_verify_offsite_backup(
            backup_dir=str(snapshot),
            output_dir=str(restore_output),
            webdav_url="unused",
            auth_mode="basic",
            user_env="UNUSED_USER",
            secret_env="UNUSED_SECRET",
            age_identity=str(identity),
            receipt_root=str(receipt_root),
            as_json=True,
            client=client,
        )
        == 0
    )
    verify_summary = json.loads(capsys.readouterr().out)
    assert verify_summary["ok"] is True
    assert (restore_output / "repo" / "README.md").read_text() == "offsite fixture\n"
    with closing(sqlite3.connect(restore_output / "server.db")) as connection:
        assert connection.execute("SELECT value FROM entries").fetchone() == ("offsite",)

    local_receipt.unlink()
    run_server_export_backups(
        backup_root=str(backup_root),
        staging_dir=str(tmp_path / "staging"),
        webdav_url="unused",
        remote_prefix="skills.infinitas.fun",
        receipt_root=str(receipt_root),
        age_recipient=recipient,
        auth_mode="basic",
        user_env="UNUSED_USER",
        secret_env="UNUSED_SECRET",
        as_json=True,
        client=client,
    )
    recovered = json.loads(capsys.readouterr().out)
    assert recovered["exports"][0]["status"] == "recovered"
    assert local_receipt.is_file()
    assert not (snapshot / RECEIPT_NAME).exists()
    client.close()


def test_inspect_backup_state_reports_missing_offsite_export(tmp_path: Path, capsys) -> None:
    backup_root, _snapshot = _create_snapshot(tmp_path)
    capsys.readouterr()

    result = run_server_inspect_backup_state(
        backup_root=str(backup_root),
        max_local_age_hours=2,
        max_offsite_age_hours=3,
        as_json=True,
    )

    summary = json.loads(capsys.readouterr().out)
    assert result == 2
    assert summary["pending_exports"] == 1
    assert summary["alerts"] == ["offsite_backup_stale"]


def test_webdav_download_follows_cross_origin_redirect_without_forwarding_auth(
    tmp_path: Path,
) -> None:
    requests: list[tuple[str, str | None]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "openlist.example":
            return httpx.Response(302, headers={"Location": "https://objects.example/backup.age"})
        return httpx.Response(200, content=b"encrypted-backup")

    client = WebDAVClient(
        base_url="https://openlist.example/dav",
        auth_mode="basic",
        username="backup-user",
        secret="test-password",
        transport=httpx.MockTransport(handle),
    )
    target = tmp_path / "backup.age"

    client.download_file("/backup.age", target)

    assert target.read_bytes() == b"encrypted-backup"
    assert requests == [
        ("openlist.example", "Basic YmFja3VwLXVzZXI6dGVzdC1wYXNzd29yZA=="),
        ("objects.example", None),
    ]
    client.close()
