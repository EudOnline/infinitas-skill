from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from infinitas_skill.release.attestation import (
    AttestationError,
    verify_ci_attestation,
)


def _make_valid_ci_provenance():
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
            "format": "ci",
            "policy_mode": "enforce",
            "require_verified_attestation_for_release_output": True,
            "require_verified_attestation_for_distribution": True,
            "namespace": "infinitas-skill",
            "allowed_signers": "config/allowed_signers",
            "signer_identity": "test-user",
            "signature_file": "provenance.json.ssig",
            "generator": "infinitas-skill-ci",
        },
        "ci": {
            "provider": "github-actions",
            "repository": "EudOnline/infinitas-skill",
            "workflow": "release-attestation",
            "run_id": "12345",
            "run_attempt": "1",
            "sha": "a" * 40,
            "ref": "refs/tags/v1.0.0",
        },
    }


def _make_attestation_config():
    return {
        "config": {},
        "format": "ssh",
        "namespace": "infinitas-skill",
        "allowed_signers_rel": "config/allowed_signers",
        "allowed_signers_path": Path("/fake/allowed_signers"),
        "signature_ext": ".ssig",
        "signing_key_env": "INFINITAS_SKILL_GIT_SIGNING_KEY",
        "policy_mode": "enforce",
        "release_trust_mode": "ssh",
        "requires_ssh_attestation": True,
        "requires_ci_attestation": False,
        "ci": {
            "provider": "github-actions",
            "issuer": None,
            "repository": "EudOnline/infinitas-skill",
            "workflow": "release-attestation",
        },
        "transparency_log": {
            "mode": "disabled",
            "endpoint": None,
            "timeout_seconds": 5,
        },
        "require_release_output": True,
    }


def test_verify_ci_attestation_rejects_invalid_json(tmp_path: Path):
    bad = tmp_path / "prov.json"
    bad.write_text("not json", encoding="utf-8")
    try:
        verify_ci_attestation(bad, root=tmp_path)
    except AttestationError as exc:
        assert "could not parse" in str(exc)


def test_verify_ci_attestation_rejects_bad_schema(tmp_path: Path):
    prov = tmp_path / "prov.json"
    prov.write_text(
        json.dumps({"kind": "wrong", "schema_version": 1}),
        encoding="utf-8",
    )
    try:
        verify_ci_attestation(prov, root=tmp_path)
    except AttestationError as exc:
        assert "kind must be skill-release-attestation" in str(exc)


def test_verify_ci_attestation_rejects_non_ci_format(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    payload["attestation"]["format"] = "ssh"
    payload["attestation"]["signature_ext"] = ".ssig"
    payload["attestation"]["signer_identity"] = "test-user"
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        try:
            verify_ci_attestation(prov, root=tmp_path)
        except AttestationError as exc:
            assert "expected CI attestation format" in str(exc)


def test_verify_ci_attestation_rejects_provider_mismatch(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    payload["ci"]["provider"] = "gitlab-ci"
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        try:
            verify_ci_attestation(prov, root=tmp_path)
        except AttestationError as exc:
            assert "ci.provider" in str(exc)
            assert "does not match" in str(exc)


def test_verify_ci_attestation_rejects_repository_mismatch(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    payload["ci"]["repository"] = "wrong/repo"
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        try:
            verify_ci_attestation(prov, root=tmp_path)
        except AttestationError as exc:
            assert "ci.repository" in str(exc)


def test_verify_ci_attestation_rejects_workflow_mismatch(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    payload["ci"]["workflow"] = "wrong-workflow"
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        try:
            verify_ci_attestation(prov, root=tmp_path)
        except AttestationError as exc:
            assert "ci.workflow" in str(exc)


def test_verify_ci_attestation_rejects_sha_git_commit_mismatch(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    payload["ci"]["sha"] = "b" * 40
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        try:
            verify_ci_attestation(prov, root=tmp_path)
        except AttestationError as exc:
            assert "ci.sha does not match git.commit" in str(exc)


def test_verify_ci_attestation_rejects_sha_snapshot_commit_mismatch(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    payload["source_snapshot"]["commit"] = "b" * 40
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        try:
            verify_ci_attestation(prov, root=tmp_path)
        except AttestationError as exc:
            assert "ci.sha does not match source_snapshot.commit" in str(exc)


def test_verify_ci_attestation_rejects_ref_snapshot_ref_mismatch(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    payload["source_snapshot"]["ref"] = "refs/tags/wrong"
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        try:
            verify_ci_attestation(prov, root=tmp_path)
        except AttestationError as exc:
            assert "ci.ref does not match source_snapshot.ref" in str(exc)


def test_verify_ci_attestation_succeeds_with_valid_payload(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        result = verify_ci_attestation(prov, root=tmp_path)

    assert result["verified"] is True
    assert result["skill"] == "test-skill"
    assert result["version"] == "1.0.0"
    assert result["provider"] == "github-actions"
    assert result["repository"] == "EudOnline/infinitas-skill"
    assert result["workflow"] == "release-attestation"
    assert result["sha"] == "a" * 40
    assert result["ref"] == "refs/tags/v1.0.0"
    assert result["format"] == "ci"


def test_verify_ci_attestation_allows_missing_ci_config_fields(tmp_path: Path):
    payload = _make_valid_ci_provenance()
    prov = tmp_path / "prov.json"
    prov.write_text(json.dumps(payload), encoding="utf-8")

    cfg = _make_attestation_config()
    cfg["ci"] = {"provider": None, "issuer": None, "repository": None, "workflow": None}

    with patch(
        "infinitas_skill.release.attestation.load_attestation_config",
        return_value=cfg,
    ):
        result = verify_ci_attestation(prov, root=tmp_path)

    assert result["verified"] is True
