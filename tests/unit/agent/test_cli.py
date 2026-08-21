from __future__ import annotations

import argparse
import json
from pathlib import Path

from infinitas_skill.agent import cli
from infinitas_skill.agent.profile import fingerprint, verifier
from infinitas_skill.install.install_manifest import write_install_manifest


def test_restore_with_explicit_base_url_is_anonymous_and_uses_exact_installer(
    monkeypatch, tmp_path: Path
) -> None:
    calls: dict[str, object] = {}

    def fail_profile(_name: str) -> dict:
        raise AssertionError("explicit --base-url must not read an Agent profile")

    def fake_bootstrap(**kwargs) -> dict:
        calls["bootstrap"] = kwargs
        return {"ok": True}

    def fake_install(**kwargs) -> int:
        calls["install"] = kwargs
        return 0

    monkeypatch.setattr(cli, "read_profile", fail_profile)
    monkeypatch.setattr(cli, "bootstrap_public_registry", fake_bootstrap)
    monkeypatch.setattr(cli, "run_install_exact", fake_install)
    args = argparse.Namespace(
        base_url="https://skills.example.test",
        profile="missing",
        registry="public",
        qualified_name="publisher/demo",
        version="1.10.0",
        target=str(tmp_path / "installed"),
        force=False,
    )

    assert cli._restore(args) == 0
    assert calls["bootstrap"] == {
        "root": (tmp_path / "installed").resolve(),
        "name": "public",
        "base_url": "https://skills.example.test/api/v1/registry",
        "set_default": True,
    }
    assert calls["install"] == {
        "root": (tmp_path / "installed").resolve(),
        "name": "publisher/demo",
        "target_dir": str((tmp_path / "installed").resolve()),
        "requested_version": "1.10.0",
        "source_registry": "public",
        "force": False,
        "as_json": True,
    }


def test_restore_without_base_url_reports_clear_profile_configuration_error(
    monkeypatch, tmp_path: Path
) -> None:
    def missing_profile(_name: str) -> dict:
        raise ValueError("missing")

    monkeypatch.setattr(cli, "read_profile", missing_profile)
    args = argparse.Namespace(
        base_url=None,
        profile="missing",
        registry="public",
        qualified_name="publisher/demo",
        version=None,
        target=str(tmp_path),
        force=False,
    )

    try:
        cli._restore(args)
    except RuntimeError as exc:
        assert "pass --base-url" in str(exc)
    else:
        raise AssertionError("restore accepted no Registry configuration")


def test_update_and_verify_reuse_install_lifecycle_services(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    write_install_manifest(
        tmp_path,
        {
            "schema_version": 1,
            "skills": {"demo": {"name": "demo", "qualified_name": "publisher/demo"}},
            "history": {},
        },
    )
    calls: dict[str, object] = {}

    def fake_upgrade(**kwargs) -> int:
        calls["upgrade"] = kwargs
        return 0

    monkeypatch.setattr(cli, "run_install_upgrade", fake_upgrade)
    update_args = argparse.Namespace(
        target=str(tmp_path),
        qualified_name="publisher/demo",
        base_url=None,
        registry="public",
        profile="default",
        force=True,
    )
    assert cli._update(update_args) == 0
    assert calls["upgrade"] == {
        "root": tmp_path.resolve(),
        "installed_name": "publisher/demo",
        "target_dir": str(tmp_path.resolve()),
        "force": True,
        "as_json": True,
    }

    monkeypatch.setattr(
        cli,
        "verify_installed_skill",
        lambda *_args, **_kwargs: {"state": "verified", "modified_count": 0},
    )
    verify_args = argparse.Namespace(target=str(tmp_path), qualified_name="publisher/demo")
    assert cli._verify(verify_args) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "verified"


def test_rotate_key_updates_profile_without_printing_raw_key(monkeypatch, capsys) -> None:
    profile = {"base_url": "https://skills.example.test", "api_key": "agt_current"}
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli, "read_profile", lambda _name: profile)
    monkeypatch.setattr(cli, "new_keys", lambda: ("status_unused", "agt_replacement"))

    def fake_request(*_args, **kwargs) -> dict:
        captured["request"] = kwargs
        return {
            "ok": True,
            "fingerprint": fingerprint(verifier("agt_replacement")),
        }

    def fake_stage(name, payload, *, expected_api_key):
        captured["stage"] = (name, payload, expected_api_key)
        return payload, True

    def fake_finalize(name):
        captured["finalize"] = name
        return Path("/profiles/default.json")

    monkeypatch.setattr(cli, "_request", fake_request)
    monkeypatch.setattr(cli, "stage_profile_rotation", fake_stage)
    monkeypatch.setattr(cli, "finalize_profile_rotation", fake_finalize)

    assert cli._rotate(argparse.Namespace(profile="default")) == 0
    output = capsys.readouterr().out
    assert "agt_current" not in output
    assert "agt_replacement" not in output
    assert captured["request"] == {
        "token": "agt_current",
        "body": {
            "api_key_verifier": verifier("agt_replacement"),
            "fingerprint": fingerprint(verifier("agt_replacement")),
        },
    }
    assert captured["finalize"] == "default"


def test_rotate_key_recovers_staged_server_accepted_key(monkeypatch, capsys) -> None:
    profile = {"base_url": "https://skills.example.test", "api_key": "agt_current"}
    staged = {**profile, "api_key": "agt_replacement", "fingerprint": "a" * 16}
    requests: list[dict[str, object]] = []
    monkeypatch.setattr(cli, "read_profile", lambda _name: profile)
    monkeypatch.setattr(cli, "new_keys", lambda: ("status_unused", "agt_unused"))
    monkeypatch.setattr(cli, "stage_profile_rotation", lambda *_args, **_kwargs: (staged, False))
    monkeypatch.setattr(
        cli,
        "_request",
        lambda *_args, **kwargs: requests.append(kwargs) or {"principal_id": 7},
    )
    monkeypatch.setattr(
        cli, "finalize_profile_rotation", lambda _name: Path("/profiles/default.json")
    )

    assert cli._rotate(argparse.Namespace(profile="default")) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["recovered"] is True
    assert requests == [{"token": "agt_replacement"}]
