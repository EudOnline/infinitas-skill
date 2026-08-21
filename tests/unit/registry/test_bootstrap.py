from __future__ import annotations

import json

import httpx

from infinitas_skill.registry.cli import build_registry_parser


def _trust_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "schema_version": 1,
            "signing": {
                "namespace": "infinitas-skill",
                "allowed_signers": "config/allowed_signers",
                "attestation": {
                    "allowed_signers": "config/allowed_signers",
                    "policy": {"mode": "enforce"},
                },
            },
            "allowed_signers": "release@example ssh-ed25519 AAAATEST\n",
            "install_integrity_policy": {
                "schema_version": 1,
                "freshness": {"stale_after_hours": 168, "stale_policy": "warn"},
            },
        },
        request=httpx.Request(
            "GET", "https://registry.example.test/api/v1/registry/trust-bootstrap.json"
        ),
    )


def test_registry_bootstrap_installs_source_and_public_trust(monkeypatch, tmp_path, capsys) -> None:
    captured = {}

    def fake_fetch(url, path, **kwargs):
        captured.update({"url": url, "path": path, **kwargs})
        return _trust_response().json()

    monkeypatch.setattr("infinitas_skill.registry.local_ops.fetch_json", fake_fetch)
    parser = build_registry_parser()
    args = parser.parse_args(
        [
            "bootstrap",
            "hosted",
            "https://registry.example.test/api/v1/registry",
            "--repo-root",
            str(tmp_path),
            "--set-default",
            "--json",
        ]
    )

    assert args._handler(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["source_changed"] is True
    assert result["trust_changed"] is True
    assert captured == {
        "url": "https://registry.example.test/api/v1/registry",
        "path": "trust-bootstrap.json",
    }

    config_dir = tmp_path / "config"
    source = json.loads((config_dir / "registry-sources.json").read_text(encoding="utf-8"))
    assert source["default_registry"] == "hosted"
    assert source["registries"][0]["auth"] == {"mode": "none"}
    assert source["registries"][0]["trust"] == "public"
    assert (config_dir / "allowed_signers").stat().st_mode & 0o777 == 0o644

    assert args._handler(args) == 0
    repeated = json.loads(capsys.readouterr().out)
    assert repeated["source_changed"] is False
    assert repeated["trust_changed"] is False


def test_registry_bootstrap_refuses_to_replace_different_trust(
    monkeypatch, tmp_path, capsys
) -> None:
    monkeypatch.setattr(
        "infinitas_skill.registry.local_ops.fetch_json",
        lambda *_args, **_kwargs: _trust_response().json(),
    )
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    signing = config_dir / "signing.json"
    signing.write_text('{"local": true}\n', encoding="utf-8")
    parser = build_registry_parser()
    args = parser.parse_args(
        [
            "bootstrap",
            "hosted",
            "https://registry.example.test/api/v1/registry",
            "--repo-root",
            str(tmp_path),
            "--json",
        ]
    )

    assert args._handler(args) == 1
    result = json.loads(capsys.readouterr().out)
    assert "different content" in result["message"]
    assert signing.read_text(encoding="utf-8") == '{"local": true}\n'
    assert not (config_dir / "registry-sources.json").exists()
