from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from infinitas_skill.openclaw.snapshot import (
    OpenClawSnapshotError,
    create_openclaw_snapshot,
    restore_openclaw_snapshot,
)


def _skill(tmp_path: Path) -> Path:
    skill = tmp_path / "teacher-work-datahub"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: teacher-work-datahub\ndescription: Teacher data.\n---\n",
        encoding="utf-8",
    )
    (skill / "scripts").mkdir()
    script = skill / "scripts" / "check.py"
    script.write_text("print('ok')\n", encoding="utf-8")
    script.chmod(0o755)
    (skill / "__pycache__").mkdir()
    (skill / "__pycache__" / "check.pyc").write_bytes(b"cache")
    (skill / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (skill / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
    return skill


def _data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    raw = data / "raw" / "2025-2026-S2"
    raw.mkdir(parents=True)
    (raw / "教师配备表.xls").write_bytes(b"binary-xls")
    (data / "catalog.json").write_text('{"records": []}\n', encoding="utf-8")
    return data


def test_data_snapshot_requires_explicit_encryption_or_plaintext_acknowledgement(
    tmp_path: Path,
) -> None:
    with pytest.raises(OpenClawSnapshotError, match="require --age-recipient"):
        create_openclaw_snapshot(
            skill_dir=_skill(tmp_path),
            data_dir=_data(tmp_path),
            output_path=tmp_path / "snapshot.tar.gz",
        )


def test_snapshot_suffix_must_match_encryption_mode(tmp_path: Path) -> None:
    with pytest.raises(OpenClawSnapshotError, match="must not end in .age"):
        create_openclaw_snapshot(
            skill_dir=_skill(tmp_path),
            output_path=tmp_path / "plaintext.age",
        )

    encrypted_root = tmp_path / "encrypted"
    encrypted_root.mkdir()
    with pytest.raises(OpenClawSnapshotError, match="must end in .age"):
        create_openclaw_snapshot(
            skill_dir=_skill(encrypted_root),
            output_path=tmp_path / "encrypted.tar.gz",
            age_recipients=["age1invalid-but-not-invoked"],
        )


def test_snapshot_sources_and_output_must_not_overlap(tmp_path: Path) -> None:
    skill = _skill(tmp_path)
    with pytest.raises(OpenClawSnapshotError, match="output must be outside"):
        create_openclaw_snapshot(skill_dir=skill, output_path=skill / "snapshot.tar.gz")

    with pytest.raises(OpenClawSnapshotError, match="directories must not overlap"):
        create_openclaw_snapshot(
            skill_dir=skill,
            data_dir=skill / "scripts",
            output_path=tmp_path / "snapshot.tar.gz",
            allow_plaintext_data=True,
        )


def test_plaintext_snapshot_round_trip_preserves_skill_and_data(tmp_path: Path) -> None:
    skill = _skill(tmp_path)
    data = _data(tmp_path)
    snapshot = tmp_path / "snapshot.tar.gz"

    created = create_openclaw_snapshot(
        skill_dir=skill,
        data_dir=data,
        output_path=snapshot,
        allow_plaintext_data=True,
    )
    restored_skill = tmp_path / "restored-skill"
    restored_data = tmp_path / "restored-data"
    restored = restore_openclaw_snapshot(
        snapshot_path=snapshot,
        skill_target=restored_skill,
        data_target=restored_data,
    )

    assert created["payloads"]["skill"]["file_count"] == 3
    assert created["payloads"]["data"]["file_count"] == 2
    assert restored["verified"] is True
    assert (restored_skill / "SKILL.md").read_bytes() == (skill / "SKILL.md").read_bytes()
    assert not (restored_skill / "__pycache__").exists()
    assert not (restored_skill / ".env").exists()
    assert (restored_skill / ".env.example").is_file()
    assert (restored_data / "raw/2025-2026-S2/教师配备表.xls").read_bytes() == b"binary-xls"
    assert (restored_skill / "scripts/check.py").stat().st_mode & 0o111


def test_restore_verify_only_does_not_require_targets(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.tar.gz"
    create_openclaw_snapshot(skill_dir=_skill(tmp_path), output_path=snapshot)

    result = restore_openclaw_snapshot(snapshot_path=snapshot, verify_only=True)

    assert result["verified"] is True
    assert result["restored"] is False


def test_restore_refuses_existing_target_without_force(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.tar.gz"
    create_openclaw_snapshot(skill_dir=_skill(tmp_path), output_path=snapshot)
    target = tmp_path / "target"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(OpenClawSnapshotError, match="target already exists"):
        restore_openclaw_snapshot(snapshot_path=snapshot, skill_target=target)

    assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_restore_rejects_overlapping_skill_and_data_targets(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.tar.gz"
    create_openclaw_snapshot(
        skill_dir=_skill(tmp_path),
        data_dir=_data(tmp_path),
        output_path=snapshot,
        allow_plaintext_data=True,
    )
    target = tmp_path / "restore"

    with pytest.raises(OpenClawSnapshotError, match="targets must not overlap"):
        restore_openclaw_snapshot(
            snapshot_path=snapshot,
            skill_target=target,
            data_target=target / "data",
        )

    assert not target.exists()


def test_restore_rejects_archive_path_escape(tmp_path: Path) -> None:
    snapshot = tmp_path / "escape.tar.gz"
    with tarfile.open(snapshot, "w:gz") as archive:
        info = tarfile.TarInfo("../escape")
        info.size = 1
        archive.addfile(info, io.BytesIO(b"x"))

    with pytest.raises(OpenClawSnapshotError, match="unsafe snapshot member path"):
        restore_openclaw_snapshot(snapshot_path=snapshot, verify_only=True)


def test_restore_rejects_manifest_checksum_mismatch(tmp_path: Path) -> None:
    snapshot = tmp_path / "tampered.tar.gz"
    manifest = {
        "schema_version": 1,
        "skill": {"name": "tampered"},
        "payloads": {},
        "files": [
            {
                "area": "skill",
                "path": "SKILL.md",
                "archive_path": "payload/skill/SKILL.md",
                "size": 1,
                "sha256": "0" * 64,
                "mode": 420,
            }
        ],
    }
    with tarfile.open(snapshot, "w:gz") as archive:
        for name, payload in (
            ("manifest.json", json.dumps(manifest).encode()),
            ("payload/skill/SKILL.md", b"x"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))

    with pytest.raises(OpenClawSnapshotError, match="checksum mismatch"):
        restore_openclaw_snapshot(snapshot_path=snapshot, verify_only=True)


def test_restore_rejects_manifest_payload_count_mismatch(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.tar.gz"
    create_openclaw_snapshot(skill_dir=_skill(tmp_path), output_path=snapshot)
    rewritten = tmp_path / "rewritten.tar.gz"
    with tarfile.open(snapshot, "r:gz") as source, tarfile.open(rewritten, "w:gz") as target:
        for member in source:
            payload = source.extractfile(member).read()
            if member.name == "manifest.json":
                manifest = json.loads(payload)
                manifest["payloads"]["skill"]["file_count"] += 1
                payload = json.dumps(manifest).encode()
                member.size = len(payload)
            target.addfile(member, io.BytesIO(payload))

    with pytest.raises(OpenClawSnapshotError, match="payload metadata mismatch"):
        restore_openclaw_snapshot(snapshot_path=rewritten, verify_only=True)


@pytest.mark.skipif(shutil.which("age") is None, reason="age is not installed")
def test_age_encrypted_snapshot_round_trip(tmp_path: Path) -> None:
    identity = tmp_path / "age-identity.txt"
    generated = subprocess.run(
        ["age-keygen", "--output", str(identity)],
        text=True,
        capture_output=True,
        check=True,
    )
    recipient = next(
        line.removeprefix("Public key: ").strip()
        for line in generated.stderr.splitlines()
        if line.startswith("Public key: ")
    )
    snapshot = tmp_path / "snapshot.tar.gz.age"
    create_openclaw_snapshot(
        skill_dir=_skill(tmp_path),
        data_dir=_data(tmp_path),
        output_path=snapshot,
        age_recipients=[recipient],
    )

    result = restore_openclaw_snapshot(
        snapshot_path=snapshot,
        skill_target=tmp_path / "restored-skill",
        data_target=tmp_path / "restored-data",
        age_identities=[str(identity)],
    )

    assert result["encrypted"] is True
    assert (tmp_path / "restored-data/raw/2025-2026-S2/教师配备表.xls").is_file()
