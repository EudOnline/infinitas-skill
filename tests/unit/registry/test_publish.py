from __future__ import annotations

import json
import stat
from pathlib import Path

import httpx
import pytest

from infinitas_skill.registry.publish import publish_skill


def _source(root: Path) -> Path:
    source = root / "adapt"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: adapt\ndescription: Adapt designs across contexts.\n---\n\n# Adapt\n",
        encoding="utf-8",
    )
    return source


def _response(status: int, payload: object) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("GET", "https://registry.example.test"),
    )


def test_publish_orchestrates_idempotent_hosted_flow(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    def fake_request(method: str, url: str, **kwargs) -> httpx.Response:
        path = url.removeprefix("https://registry.example.test")
        calls.append((method, path))
        if path == "/api/v1/access/me":
            return _response(200, {"principal_slug": "tdcasual"})
        if path == "/api/v1/skills?slug=adapt":
            return _response(200, [])
        if method == "POST" and path == "/api/v1/skills":
            return _response(201, {"id": 8, "slug": "adapt", "status": "active"})
        if method == "GET" and path == "/api/v1/skills/8/versions":
            return _response(200, [])
        if method == "POST" and path == "/api/v1/skills/8/content":
            return _response(201, {"content_id": "cnt_adapt"})
        if method == "POST" and path == "/api/v1/skills/8/versions":
            return _response(
                201,
                {"id": 10, "version": "1.0.0", "content_digest": "sha256:bundle"},
            )
        if method == "POST" and path == "/api/v1/versions/10/releases":
            return _response(201, {"id": 11, "skill_version_id": 10, "state": "preparing"})
        if path == "/api/v1/releases/11":
            return _response(200, {"id": 11, "state": "ready"})
        if method == "GET" and path == "/api/v1/releases/11/exposures":
            return _response(200, [])
        if method == "POST" and path == "/api/v1/releases/11/exposures":
            return _response(201, {"id": 12, "release_id": 11, "audience_type": "private"})
        raise AssertionError(f"unexpected request {method} {path} {kwargs}")

    monkeypatch.setattr(httpx, "request", fake_request)
    result = publish_skill(
        _source(tmp_path),
        base_url="https://registry.example.test",
        token="publisher-token",
        version="1.0.0",
        repo_root=Path.cwd(),
        timeout_seconds=2,
    ).payload

    assert result["state"] == "published"
    assert result["skill"]["id"] == 8
    assert result["version"]["id"] == 10
    assert result["release"]["state"] == "ready"
    assert result["exposure"]["audience_type"] == "private"
    assert result["reused_version"] is False
    assert calls.count(("GET", "/api/v1/access/me")) == 1
    receipt_path = Path(result["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["state"] == "published"
    assert "token" not in receipt
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600


def test_publish_dry_run_does_not_mutate_registry(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    def fake_request(method: str, url: str, **_kwargs) -> httpx.Response:
        calls.append(f"{method} {url}")
        return _response(200, {"principal_slug": "tdcasual"})

    monkeypatch.setattr(httpx, "request", fake_request)
    result = publish_skill(
        _source(tmp_path),
        base_url="https://registry.example.test",
        token="publisher-token",
        version="1.0.0",
        repo_root=Path.cwd(),
        dry_run=True,
    ).payload

    assert result["state"] == "dry-run"
    assert result["prepared"]["qualified_name"] == "tdcasual/adapt"
    assert len(calls) == 1
    assert json.dumps(result, sort_keys=True)
    assert not (tmp_path / "state").exists()


def test_publish_no_wait_stops_before_exposure_for_preparing_release(
    monkeypatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, str]] = []
    receipt_path = tmp_path / "publish-receipt.json"

    def fake_request(method: str, url: str, **kwargs) -> httpx.Response:
        path = url.removeprefix("https://registry.example.test")
        calls.append((method, path))
        if path == "/api/v1/access/me":
            return _response(200, {"principal_slug": "tdcasual"})
        if path == "/api/v1/skills?slug=adapt":
            return _response(200, [{"id": 8, "slug": "adapt", "status": "active"}])
        if method == "GET" and path == "/api/v1/skills/8/versions":
            return _response(200, [])
        if method == "POST" and path == "/api/v1/skills/8/content":
            return _response(201, {"content_id": "cnt_adapt"})
        if method == "POST" and path == "/api/v1/skills/8/versions":
            return _response(201, {"id": 10, "version": "1.0.0"})
        if method == "POST" and path == "/api/v1/versions/10/releases":
            return _response(201, {"id": 11, "state": "preparing"})
        raise AssertionError(f"unexpected request {method} {path} {kwargs}")

    monkeypatch.setattr(httpx, "request", fake_request)
    result = publish_skill(
        _source(tmp_path),
        base_url="https://registry.example.test",
        token="publisher-token",
        version="1.0.0",
        repo_root=Path.cwd(),
        wait=False,
        receipt_path=receipt_path,
    ).payload

    assert result["state"] == "release-created"
    assert result["release"]["state"] == "preparing"
    assert result["exposure"] is None
    assert not any(path.endswith("/exposures") for _method, path in calls)
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["state"] == "release-created"


def test_publish_resume_reuses_uploaded_content(monkeypatch, tmp_path: Path) -> None:
    source = _source(tmp_path)
    receipt_path = tmp_path / "publish-receipt.json"
    upload_count = 0
    release_attempts = 0

    def fake_request(method: str, url: str, **_kwargs) -> httpx.Response:
        nonlocal release_attempts, upload_count
        path = url.removeprefix("https://registry.example.test")
        if path == "/api/v1/access/me":
            return _response(200, {"principal_slug": "tdcasual"})
        if path == "/api/v1/skills?slug=adapt":
            return _response(200, [{"id": 8, "slug": "adapt", "status": "active"}])
        if method == "GET" and path == "/api/v1/skills/8/versions":
            return _response(200, [])
        if method == "POST" and path == "/api/v1/skills/8/content":
            upload_count += 1
            return _response(201, {"content_id": "cnt_resume"})
        if method == "POST" and path == "/api/v1/skills/8/versions":
            release_attempts += 1
            if release_attempts == 1:
                raise httpx.ConnectError("connection lost after upload")
            return _response(201, {"id": 10, "version": "1.0.0"})
        if method == "POST" and path == "/api/v1/versions/10/releases":
            return _response(201, {"id": 11, "state": "ready"})
        if path == "/api/v1/releases/11":
            return _response(200, {"id": 11, "state": "ready"})
        if method == "GET" and path == "/api/v1/releases/11/exposures":
            return _response(200, [{"id": 12, "audience_type": "private", "state": "active"}])
        raise AssertionError(f"unexpected request {method} {path}")

    monkeypatch.setattr(httpx, "request", fake_request)
    with pytest.raises(RuntimeError, match="connection lost after upload"):
        publish_skill(
            source,
            base_url="https://registry.example.test",
            token="publisher-token",
            version="1.0.0",
            repo_root=Path.cwd(),
            receipt_path=receipt_path,
        )

    result = publish_skill(
        source,
        base_url="https://registry.example.test",
        token="publisher-token",
        version="1.0.0",
        repo_root=Path.cwd(),
        receipt_path=receipt_path,
        resume=True,
    ).payload

    assert result["state"] == "published"
    assert upload_count == 1
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["state"] == "published"


def test_publish_resume_rejects_changed_source(monkeypatch, tmp_path: Path) -> None:
    source = _source(tmp_path)
    receipt_path = tmp_path / "publish-receipt.json"
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *_args, **_kwargs: _response(200, {"principal_slug": "tdcasual"}),
    )
    publish_skill(
        source,
        base_url="https://registry.example.test",
        token="publisher-token",
        version="1.0.0",
        repo_root=Path.cwd(),
        receipt_path=receipt_path,
        dry_run=True,
    )
    # A receipt is intentionally created directly to model a previously interrupted run.
    receipt_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_path": str(source.resolve()),
                "base_url": "https://registry.example.test",
                "qualified_name": "tdcasual/adapt",
                "version": "1.0.0",
                "bundle_sha256": "sha256:not-current",
                "state": "prepared",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="bundle_sha256"):
        publish_skill(
            source,
            base_url="https://registry.example.test",
            token="publisher-token",
            version="1.0.0",
            repo_root=Path.cwd(),
            receipt_path=receipt_path,
            resume=True,
        )
