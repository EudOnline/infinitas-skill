from __future__ import annotations

import hashlib
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
    source = _source(tmp_path)
    long_summary = "Traceable workspace data and immutable source records. " * 6
    (source / "_meta.json").write_text(
        json.dumps({"summary": long_summary}),
        encoding="utf-8",
    )

    def fake_request(method: str, url: str, **kwargs) -> httpx.Response:
        assert kwargs["headers"]["Accept"] == "application/json"
        path = url.removeprefix("https://registry.example.test")
        calls.append((method, path))
        if path == "/api/v1/access/me":
            return _response(200, {"principal_slug": "tdcasual"})
        if path == "/api/v1/skills?slug=adapt":
            return _response(200, [])
        if method == "POST" and path == "/api/v1/skills":
            assert kwargs["json"]["display_name"] == "adapt"
            assert kwargs["json"]["summary"] == long_summary
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
        source,
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


def test_publish_dry_run_with_publisher_is_fully_offline(monkeypatch, tmp_path: Path) -> None:
    source = _source(tmp_path)
    (source / ".pytest_cache").mkdir()
    (source / ".pytest_cache" / "CACHEDIR.TAG").write_text("cache", encoding="utf-8")
    (source / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (source / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
    (source / "data.json").write_text('{"critical": true}\n', encoding="utf-8")

    def unexpected_request(*_args, **_kwargs):
        raise AssertionError("offline dry-run must not contact a Registry")

    monkeypatch.setattr(httpx, "request", unexpected_request)
    result = publish_skill(
        source,
        base_url="https://registry.invalid",
        token="",
        version="1.0.0",
        repo_root=Path.cwd(),
        dry_run=True,
        publisher="tdcasual",
    ).payload

    assert result["state"] == "dry-run"
    assert result["prepared"]["qualified_name"] == "tdcasual/adapt"
    assert result["prepared"]["included_file_count"] == 6
    assert result["prepared"]["included_expanded_bytes"] > 0
    assert result["prepared"]["included_paths"] == [
        ".env.example",
        "CHANGELOG.md",
        "SKILL.md",
        "_meta.json",
        "data.json",
        "tests/smoke.md",
    ]
    assert result["prepared"]["excluded_paths"] == []


def test_publish_rejects_publisher_override_for_live_write(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="only supported with dry_run"):
        publish_skill(
            _source(tmp_path),
            base_url="https://registry.invalid",
            token="publisher-token",
            version="1.0.0",
            repo_root=Path.cwd(),
            publisher="tdcasual",
        )


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


def test_agent_publish_waits_for_intent_activation(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def fake_request(method: str, url: str, **_kwargs) -> httpx.Response:
        path = url.removeprefix("https://registry.example.test")
        calls.append((method, path))
        responses = {
            "/api/v1/access/me": {"principal_slug": "backup-agent"},
            "/api/v1/skills?slug=adapt": [{"id": 8, "slug": "adapt"}],
            "/api/v1/skills/8/versions": [],
        }
        if method == "GET" and path in responses:
            return _response(200, responses[path])
        if method == "POST" and path == "/api/v1/skills/8/content":
            return _response(201, {"content_id": "cnt_agent"})
        if method == "POST" and path == "/api/v1/skills/8/versions":
            return _response(201, {"id": 10, "version": "1.0.0"})
        if method == "POST" and path == "/api/v1/agent/versions/10/publish":
            return _response(202, {"id": 11, "state": "preparing"})
        if path == "/api/v1/releases/11":
            return _response(200, {"id": 11, "state": "ready"})
        if path == "/api/v1/agent/publish-intents/11":
            return _response(
                200,
                {"intent_id": 12, "release_id": 11, "release_state": "ready", "state": "activated"},
            )
        raise AssertionError(f"unexpected request {method} {path}")

    monkeypatch.setattr(httpx, "request", fake_request)
    result = publish_skill(
        _source(tmp_path),
        base_url="https://registry.example.test",
        token="agent-token",
        version="1.0.0",
        repo_root=Path.cwd(),
        agent_mode=True,
    ).payload

    assert result["state"] == "published"
    assert result["publish_intent"]["state"] == "activated"
    assert ("GET", "/api/v1/agent/publish-intents/11") in calls


def test_agent_publish_reports_suppressed_intent(monkeypatch, tmp_path: Path) -> None:
    def fake_request(method: str, url: str, **_kwargs) -> httpx.Response:
        path = url.removeprefix("https://registry.example.test")
        if path == "/api/v1/access/me":
            return _response(200, {"principal_slug": "backup-agent"})
        if path == "/api/v1/skills?slug=adapt":
            return _response(200, [{"id": 8, "slug": "adapt"}])
        if method == "GET" and path == "/api/v1/skills/8/versions":
            return _response(200, [])
        if method == "POST" and path == "/api/v1/skills/8/content":
            return _response(201, {"content_id": "cnt_agent"})
        if method == "POST" and path == "/api/v1/skills/8/versions":
            return _response(201, {"id": 10, "version": "1.0.0"})
        if method == "POST" and path == "/api/v1/agent/versions/10/publish":
            return _response(202, {"id": 11, "state": "preparing"})
        if path == "/api/v1/releases/11":
            return _response(200, {"id": 11, "state": "ready"})
        if path == "/api/v1/agent/publish-intents/11":
            return _response(
                200,
                {
                    "intent_id": 12,
                    "release_id": 11,
                    "release_state": "ready",
                    "state": "suppressed",
                    "reason": "auto public publish is disabled",
                },
            )
        raise AssertionError(f"unexpected request {method} {path}")

    monkeypatch.setattr(httpx, "request", fake_request)
    with pytest.raises(RuntimeError, match="suppressed: auto public publish is disabled"):
        publish_skill(
            _source(tmp_path),
            base_url="https://registry.example.test",
            token="agent-token",
            version="1.0.0",
            repo_root=Path.cwd(),
            agent_mode=True,
        )


def test_agent_publish_without_wait_does_not_report_pending_intent_as_published(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_request(method: str, url: str, **_kwargs) -> httpx.Response:
        path = url.removeprefix("https://registry.example.test")
        responses = {
            "/api/v1/access/me": {"principal_slug": "backup-agent"},
            "/api/v1/skills?slug=adapt": [{"id": 8, "slug": "adapt"}],
            "/api/v1/skills/8/versions": [],
        }
        if method == "GET" and path in responses:
            return _response(200, responses[path])
        if method == "POST" and path == "/api/v1/skills/8/content":
            return _response(201, {"content_id": "cnt_agent"})
        if method == "POST" and path == "/api/v1/skills/8/versions":
            return _response(201, {"id": 10, "version": "1.0.0"})
        if method == "POST" and path == "/api/v1/agent/versions/10/publish":
            return _response(200, {"id": 11, "state": "ready"})
        if path == "/api/v1/agent/publish-intents/11":
            return _response(
                200,
                {"intent_id": 12, "release_id": 11, "release_state": "ready", "state": "pending"},
            )
        raise AssertionError(f"unexpected request {method} {path}")

    monkeypatch.setattr(httpx, "request", fake_request)
    result = publish_skill(
        _source(tmp_path),
        base_url="https://registry.example.test",
        token="agent-token",
        version="1.0.0",
        repo_root=Path.cwd(),
        wait=False,
        agent_mode=True,
    ).payload

    assert result["state"] == "release-created"
    assert result["publish_intent"]["state"] == "pending"


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


def test_publish_reloads_same_digest_after_concurrent_version_conflict(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    source = _source(tmp_path)
    bundle_digest = ""

    def fake_request(method: str, url: str, **kwargs) -> httpx.Response:
        nonlocal bundle_digest
        path = url.removeprefix("https://registry.example.test")
        if path == "/api/v1/access/me":
            return _response(200, {"principal_slug": "tdcasual"})
        if path == "/api/v1/skills?slug=adapt":
            return _response(200, [{"id": 8, "slug": "adapt", "status": "active"}])
        if method == "GET" and path == "/api/v1/skills/8/versions":
            return _response(200, [])
        if method == "POST" and path == "/api/v1/skills/8/content":
            bundle_digest = hashlib.sha256(kwargs["content"]).hexdigest()
            return _response(201, {"content_id": "cnt_concurrent"})
        if method == "POST" and path == "/api/v1/skills/8/versions":
            return _response(409, {"detail": "skill version already exists"})
        if method == "GET" and path == "/api/v1/skills/8/versions/1.0.0":
            return _response(
                200,
                {
                    "id": 10,
                    "version": "1.0.0",
                    "content_digest": f"sha256:{bundle_digest}",
                },
            )
        if method == "POST" and path == "/api/v1/versions/10/releases":
            return _response(201, {"id": 11, "state": "ready"})
        if path == "/api/v1/releases/11":
            return _response(200, {"id": 11, "state": "ready"})
        if method == "GET" and path == "/api/v1/releases/11/exposures":
            return _response(200, [{"id": 12, "audience_type": "private", "state": "active"}])
        raise AssertionError(f"unexpected request {method} {path}")

    monkeypatch.setattr(httpx, "request", fake_request)
    result = publish_skill(
        source,
        base_url="https://registry.example.test",
        token="publisher-token",
        version="1.0.0",
        repo_root=Path.cwd(),
    ).payload

    assert result["state"] == "published"
    assert result["reused_version"] is True
