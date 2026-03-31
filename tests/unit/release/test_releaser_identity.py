from __future__ import annotations

import json
from pathlib import Path

from infinitas_skill.release.attestation_state import (
    TransparencyLogError,
    collect_transparency_log_state,
)
from infinitas_skill.release.policy_state import resolve_releaser_identity


def test_resolve_releaser_identity_prefers_environment_override(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("INFINITAS_SKILL_RELEASER", "release-bot")
    monkeypatch.setattr(
        "infinitas_skill.release.policy_state.git_config_value",
        lambda root, key: "ignored@example.com",
    )

    assert resolve_releaser_identity(tmp_path) == "release-bot"


def test_collect_transparency_log_state_reports_verification_errors(
    monkeypatch, tmp_path: Path
) -> None:
    meta = {"name": "demo-skill", "version": "1.2.3"}
    provenance = tmp_path / "catalog" / "provenance" / "demo-skill-1.2.3.json"
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(
        json.dumps(
            {
                "transparency_log": {
                    "mode": "rekor",
                    "required": True,
                    "entry_path": "catalog/transparency/demo-skill-1.2.3.json",
                }
            }
        ),
        encoding="utf-8",
    )

    def fail_summary(path, *, payload, root):
        raise TransparencyLogError("proof mismatch")

    monkeypatch.setattr(
        "infinitas_skill.release.attestation_state.summarize_transparency_log_state",
        fail_summary,
    )

    summary = collect_transparency_log_state(tmp_path, meta)

    assert summary["mode"] == "rekor"
    assert summary["required"] is True
    assert summary["published"] is False
    assert summary["verified"] is False
    assert summary["entry_path"] == "catalog/transparency/demo-skill-1.2.3.json"
    assert summary["error"] == "proof mismatch"
