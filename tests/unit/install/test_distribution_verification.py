from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from unittest.mock import patch

from infinitas_skill.install.distribution import (
    DistributionError,
    _normalize_build,
    _normalize_file_manifest,
    verify_distribution_manifest,
)
from infinitas_skill.release.attestation import AttestationError


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_minimal_manifest(*, bundle_sha256="abc", bundle_size=100):
    return {
        "kind": "skill-distribution-manifest",
        "schema_version": 1,
        "skill": {"name": "test-skill", "version": "1.0.0"},
        "source_snapshot": {
            "kind": "tag",
            "tag": "v1.0.0",
            "ref": "refs/tags/v1.0.0",
            "commit": "a" * 40,
            "immutable": True,
            "pushed": True,
        },
        "bundle": {
            "path": "bundle.tar.gz",
            "format": "tar.gz",
            "sha256": bundle_sha256,
            "root_dir": "test-skill",
            "size": bundle_size,
            "file_count": 1,
        },
        "attestation_bundle": {
            "provenance_path": "provenance.json",
            "signature_path": "provenance.json.ssig",
            "provenance_sha256": "psha",
            "signature_sha256": "ssha",
            "namespace": "infinitas-skill",
            "allowed_signers": "config/allowed_signers",
            "required_formats": ["ssh"],
        },
        "registry": {"registries_consulted": [], "resolved": []},
        "dependencies": {"steps": [], "registries_consulted": []},
    }


def _make_minimal_provenance():
    return {
        "kind": "skill-release-attestation",
        "schema_version": 1,
        "skill": {
            "name": "test-skill",
            "version": "1.0.0",
            "path": "skills/active/test-skill",
        },
        "git": {
            "commit": "a" * 40,
            "expected_tag": "v1.0.0",
            "release_ref": "refs/tags/v1.0.0",
            "signed_tag_verified": True,
        },
        "source_snapshot": {
            "tag": "v1.0.0",
            "ref": "refs/tags/v1.0.0",
            "commit": "a" * 40,
            "immutable": True,
            "pushed": True,
        },
        "registry": {"registries_consulted": [], "resolved": []},
        "dependencies": {"steps": [], "registries_consulted": []},
        "review": {"reviewers": []},
        "release": {
            "releaser_identity": "test-user",
            "transfer_required": False,
            "transfer_authorized": False,
            "authorized_signers": [],
            "authorized_releasers": [],
            "transfer_matches": [],
            "competing_claims": [],
        },
        "attestation": {
            "format": "ssh",
            "policy_mode": "enforce",
            "require_verified_attestation_for_release_output": True,
            "namespace": "infinitas-skill",
            "allowed_signers": "config/allowed_signers",
            "signer_identity": "test-user",
            "signature_file": "provenance.json.ssig",
        },
        "distribution": {
            "bundle": {
                "path": "bundle.tar.gz",
                "sha256": "abc",
                "format": "tar.gz",
                "root_dir": "test-skill",
            },
        },
    }


def _write_tar_gz(path: Path, entries: dict[str, bytes]):
    with tarfile.open(path, "w:gz") as tar:
        for name, content in entries.items():
            import io

            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))


def test_verify_distribution_manifest_rejects_invalid_json(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("not json", encoding="utf-8")
    with patch(
        "infinitas_skill.install.distribution.verify_attestation"
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest(str(manifest), root=tmp_path)
        except DistributionError as exc:
            assert "could not parse" in str(exc)


def test_verify_distribution_manifest_rejects_bad_schema(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"kind": "wrong"}), encoding="utf-8")
    with patch(
        "infinitas_skill.install.distribution.verify_attestation"
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest(str(manifest), root=tmp_path)
        except DistributionError as exc:
            assert "kind must be skill-distribution-manifest" in str(exc)


def test_verify_distribution_manifest_rejects_missing_provenance(tmp_path: Path):
    payload = _make_minimal_manifest()
    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with patch(
        "infinitas_skill.install.distribution.verify_attestation"
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "missing attestation payload" in str(exc)


def test_verify_distribution_manifest_rejects_missing_signature(tmp_path: Path):
    payload = _make_minimal_manifest()
    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    provenance = _make_minimal_provenance()
    provenance_bytes = json.dumps(provenance).encode("utf-8")
    (tmp_path / "provenance.json").write_bytes(provenance_bytes)
    with patch(
        "infinitas_skill.install.distribution.verify_attestation"
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "missing attestation signature" in str(exc)


def test_verify_distribution_manifest_rejects_missing_bundle(tmp_path: Path):
    payload = _make_minimal_manifest()
    provenance = _make_minimal_provenance()
    provenance_bytes = json.dumps(provenance).encode("utf-8")
    sig_bytes = b"fake-signature"

    psha = _sha256(provenance_bytes)
    ssha = _sha256(sig_bytes)

    payload["attestation_bundle"]["provenance_sha256"] = psha
    payload["attestation_bundle"]["signature_sha256"] = ssha

    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "provenance.json").write_bytes(provenance_bytes)
    (tmp_path / "provenance.json.ssig").write_bytes(sig_bytes)

    with patch(
        "infinitas_skill.install.distribution.verify_attestation"
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "missing distribution bundle" in str(exc)


def test_verify_distribution_manifest_rejects_digest_mismatch(tmp_path: Path):
    payload = _make_minimal_manifest()
    provenance = _make_minimal_provenance()
    provenance_bytes = json.dumps(provenance).encode("utf-8")
    sig_bytes = b"fake-signature"
    bundle_bytes = b"bundle-content"

    payload["attestation_bundle"]["provenance_sha256"] = "wrong-digest"
    payload["attestation_bundle"]["signature_sha256"] = _sha256(sig_bytes)
    payload["bundle"]["sha256"] = _sha256(bundle_bytes)
    payload["bundle"]["size"] = len(bundle_bytes)

    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "provenance.json").write_bytes(provenance_bytes)
    (tmp_path / "provenance.json.ssig").write_bytes(sig_bytes)
    (tmp_path / "bundle.tar.gz").write_bytes(bundle_bytes)

    with patch(
        "infinitas_skill.install.distribution.verify_attestation"
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "digest does not match" in str(exc)


def test_verify_distribution_manifest_rejects_bundle_size_mismatch(tmp_path: Path):
    bundle_content = b"test-bundle-content"
    provenance = _make_minimal_provenance()
    provenance_bytes = json.dumps(provenance).encode("utf-8")
    sig_bytes = b"sig"

    payload = _make_minimal_manifest(
        bundle_sha256=_sha256(bundle_content),
        bundle_size=9999,
    )
    payload["attestation_bundle"]["provenance_sha256"] = _sha256(provenance_bytes)
    payload["attestation_bundle"]["signature_sha256"] = _sha256(sig_bytes)

    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "provenance.json").write_bytes(provenance_bytes)
    (tmp_path / "provenance.json.ssig").write_bytes(sig_bytes)
    (tmp_path / "bundle.tar.gz").write_bytes(bundle_content)

    with patch(
        "infinitas_skill.install.distribution.verify_attestation"
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "bundle size" in str(exc)


def test_verify_distribution_manifest_rejects_attestation_error(tmp_path: Path):
    bundle_content = b"test-bundle-content"
    provenance = _make_minimal_provenance()
    provenance_bytes = json.dumps(provenance).encode("utf-8")
    sig_bytes = b"sig"

    payload = _make_minimal_manifest(
        bundle_sha256=_sha256(bundle_content),
        bundle_size=len(bundle_content),
    )
    payload["attestation_bundle"]["provenance_sha256"] = _sha256(provenance_bytes)
    payload["attestation_bundle"]["signature_sha256"] = _sha256(sig_bytes)

    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "provenance.json").write_bytes(provenance_bytes)
    (tmp_path / "provenance.json.ssig").write_bytes(sig_bytes)
    (tmp_path / "bundle.tar.gz").write_bytes(bundle_content)

    with patch(
        "infinitas_skill.install.distribution.verify_attestation",
        side_effect=AttestationError("SSH verification failed"),
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "SSH verification failed" in str(exc)


def test_verify_distribution_manifest_rejects_name_mismatch(tmp_path: Path):
    bundle_content = b"test-bundle-content"
    provenance = _make_minimal_provenance()
    provenance["skill"]["name"] = "wrong-skill"
    provenance_bytes = json.dumps(provenance).encode("utf-8")
    sig_bytes = b"sig"

    payload = _make_minimal_manifest(
        bundle_sha256=_sha256(bundle_content),
        bundle_size=len(bundle_content),
    )
    payload["attestation_bundle"]["provenance_sha256"] = _sha256(provenance_bytes)
    payload["attestation_bundle"]["signature_sha256"] = _sha256(sig_bytes)

    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "provenance.json").write_bytes(provenance_bytes)
    (tmp_path / "provenance.json.ssig").write_bytes(sig_bytes)
    (tmp_path / "bundle.tar.gz").write_bytes(bundle_content)

    mock_result = {"verified": True, "formats_verified": ["ssh"]}
    with patch(
        "infinitas_skill.install.distribution.verify_attestation",
        return_value=mock_result,
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "skill.name does not match" in str(exc)


def test_verify_distribution_manifest_rejects_registry_mismatch(tmp_path: Path):
    bundle_content = b"test-bundle-content"
    provenance = _make_minimal_provenance()
    provenance["registry"] = {"registries_consulted": ["other"], "resolved": []}
    provenance["distribution"]["bundle"]["sha256"] = _sha256(bundle_content)
    provenance_bytes = json.dumps(provenance).encode("utf-8")
    sig_bytes = b"sig"

    payload = _make_minimal_manifest(
        bundle_sha256=_sha256(bundle_content),
        bundle_size=len(bundle_content),
    )
    payload["attestation_bundle"]["provenance_sha256"] = _sha256(provenance_bytes)
    payload["attestation_bundle"]["signature_sha256"] = _sha256(sig_bytes)

    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "provenance.json").write_bytes(provenance_bytes)
    (tmp_path / "provenance.json.ssig").write_bytes(sig_bytes)
    (tmp_path / "bundle.tar.gz").write_bytes(bundle_content)

    mock_result = {"verified": True, "formats_verified": ["ssh"]}
    with patch(
        "infinitas_skill.install.distribution.verify_attestation",
        return_value=mock_result,
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "registry context does not match" in str(exc)


def test_verify_distribution_manifest_rejects_missing_distribution_bundle_metadata(
    tmp_path: Path,
):
    bundle_content = b"test-bundle-content"
    provenance = _make_minimal_provenance()
    del provenance["distribution"]["bundle"]
    provenance_bytes = json.dumps(provenance).encode("utf-8")
    sig_bytes = b"sig"

    payload = _make_minimal_manifest(
        bundle_sha256=_sha256(bundle_content),
        bundle_size=len(bundle_content),
    )
    payload["attestation_bundle"]["provenance_sha256"] = _sha256(provenance_bytes)
    payload["attestation_bundle"]["signature_sha256"] = _sha256(sig_bytes)

    (tmp_path / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "provenance.json").write_bytes(provenance_bytes)
    (tmp_path / "provenance.json.ssig").write_bytes(sig_bytes)
    (tmp_path / "bundle.tar.gz").write_bytes(bundle_content)

    mock_result = {"verified": True, "formats_verified": ["ssh"]}
    with patch(
        "infinitas_skill.install.distribution.verify_attestation",
        return_value=mock_result,
    ), patch("infinitas_skill.install.distribution.ROOT", tmp_path):
        try:
            verify_distribution_manifest("manifest.json", root=tmp_path)
        except DistributionError as exc:
            assert "missing distribution.bundle" in str(exc)


def test_normalize_file_manifest_returns_none_for_non_list():
    assert _normalize_file_manifest(None) is None
    assert _normalize_file_manifest("string") is None


def test_normalize_file_manifest_normalizes_entries():
    manifest = [{"path": "b.txt"}, {"path": "a.txt"}]
    result = _normalize_file_manifest(manifest)
    assert [e["path"] for e in result] == ["a.txt", "b.txt"]


def test_normalize_build_returns_none_for_non_dict():
    assert _normalize_build(None) is None
    assert _normalize_build("string") is None


def test_normalize_build_strips_builder_when_requested():
    result = _normalize_build(
        {"builder": "uv", "archive_format": "tar.gz"}, include_builder=False
    )
    assert "builder" not in result
    assert result["archive_format"] == "tar.gz"


def test_normalize_build_keeps_builder_by_default():
    result = _normalize_build({"builder": "uv", "archive_format": "tar.gz"})
    assert result["builder"] == "uv"
