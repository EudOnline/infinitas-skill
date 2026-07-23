from __future__ import annotations

import json

import httpx

from infinitas_skill.registry.cli import build_registry_parser


def _response(payload: dict) -> httpx.Response:
    return httpx.Response(
        201,
        json=payload,
        request=httpx.Request("POST", "https://registry.example.test"),
    )


def test_upload_content_sends_binary_gzip(monkeypatch, tmp_path, capsys) -> None:
    bundle = tmp_path / "skill.tar.gz"
    bundle.write_bytes(b"bundle-bytes")
    captured: dict = {}

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return _response({"content_id": "cnt_fixture"})

    monkeypatch.setattr(httpx, "request", fake_request)
    parser = build_registry_parser()
    args = parser.parse_args(
        [
            "--base-url",
            "https://registry.example.test/",
            "--token",
            "publisher-token",
            "skills",
            "upload-content",
            "7",
            str(bundle),
        ]
    )
    assert args._handler(args) == 0
    assert captured["method"] == "POST"
    assert captured["url"] == "https://registry.example.test/api/v1/skills/7/content"
    assert captured["content"] == b"bundle-bytes"
    assert captured["headers"] == {
        "Content-Type": "application/gzip",
        "Authorization": "Bearer publisher-token",
    }
    assert json.loads(capsys.readouterr().out)["content_id"] == "cnt_fixture"


def test_create_version_sends_only_hosted_content_contract(monkeypatch, capsys) -> None:
    captured: dict = {}

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return _response({"id": 9})

    monkeypatch.setattr(httpx, "request", fake_request)
    parser = build_registry_parser()
    args = parser.parse_args(
        [
            "versions",
            "create",
            "7",
            "--version",
            "1.2.3",
            "--content-id",
            "cnt_fixture",
        ]
    )
    assert args._handler(args) == 0
    assert captured["json"] == {
        "version": "1.2.3",
        "content_id": "cnt_fixture",
    }
    assert json.loads(capsys.readouterr().out)["id"] == 9


def test_create_exposure_omits_to_skill_default_visibility(monkeypatch, capsys) -> None:
    captured: dict = {}

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return _response({"id": 12, "audience_type": "grant"})

    monkeypatch.setattr(httpx, "request", fake_request)
    parser = build_registry_parser()
    args = parser.parse_args(["exposures", "create", "8"])

    assert args._handler(args) == 0
    assert captured["json"] == {
        "listing_mode": "listed",
        "install_mode": "enabled",
        "requested_review_mode": "none",
    }
    assert json.loads(capsys.readouterr().out)["audience_type"] == "grant"


def test_create_share_reads_password_from_env_and_returns_agent_command(
    monkeypatch, capsys
) -> None:
    captured: dict = {}
    monkeypatch.setenv("TEST_SHARE_PASSWORD", "temporary-password")

    def fake_request(method, url, **kwargs):
        captured.update({"method": method, "url": url, **kwargs})
        return _response(
            {
                "id": 14,
                "has_password": True,
                "resolve_url": "https://registry.example.test/api/v1/share-links/14/resolve",
            }
        )

    monkeypatch.setattr(httpx, "request", fake_request)
    parser = build_registry_parser()
    args = parser.parse_args(
        [
            "shares",
            "create",
            "8",
            "--name",
            "agent-demo",
            "--password-env",
            "TEST_SHARE_PASSWORD",
            "--max-uses",
            "2",
        ]
    )

    assert args._handler(args) == 0
    assert captured["url"].endswith("/api/v1/share-links/releases/8/share-links")
    assert captured["json"] == {
        "name": "agent-demo",
        "password": "temporary-password",
        "max_uses": 2,
    }
    output = json.loads(capsys.readouterr().out)
    assert output["credential_env"] == "INFINITAS_SHARE_PASSWORD"
    assert "infinitas install from-share" in output["agent_install_command"]
    assert "temporary-password" not in output["agent_install_command"]
