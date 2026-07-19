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
