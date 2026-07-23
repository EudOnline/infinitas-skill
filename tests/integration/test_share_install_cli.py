from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

import httpx
import pytest

from infinitas_skill.install.hosted_share import HostedShareError, run_install_from_share
from tests.integration.conftest import _prepare_library_client
from tests.integration.test_object_tokens_api import _prepared_object_and_release


def _bridge_response(response, url: str) -> httpx.Response:
    return httpx.Response(
        response.status_code,
        content=response.content,
        headers=dict(response.headers),
        request=httpx.Request("GET", url),
    )


def test_share_installs_verified_release_without_persisting_credentials(
    monkeypatch,
    tmp_path: Path,
    temp_repo_copy: Path,
    signing_key: Path,
) -> None:
    client = _prepare_library_client(
        monkeypatch,
        tmp_path=tmp_path,
        temp_repo_copy=temp_repo_copy,
        signing_key=signing_key,
    )
    headers = {"Authorization": "Bearer fixture-maintainer-token"}
    _object_id, release_id = _prepared_object_and_release(client, headers=headers)
    created = client.post(
        f"/api/v1/share-links/releases/{release_id}/share-links",
        headers=headers,
        json={"name": "agent-install", "max_uses": 2},
    )
    assert created.status_code == 201, created.text
    share = created.json()

    def request(method: str, url: str, **kwargs) -> httpx.Response:
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        response = client.request(
            method,
            path,
            headers=kwargs.get("headers"),
            json=kwargs.get("json"),
        )
        return _bridge_response(response, url)

    monkeypatch.setattr(httpx, "request", request)
    monkeypatch.setattr(httpx, "get", lambda url, **kwargs: request("GET", url, **kwargs))
    monkeypatch.setenv("TEST_SHARE_SECRET", share["resolve_secret"])
    target = tmp_path / "agent-skills"

    return_code = run_install_from_share(
        root=temp_repo_copy,
        resolve_url=share["resolve_url"],
        target_dir=str(target),
        secret_env="TEST_SHARE_SECRET",
        as_json=True,
    )

    assert return_code == 0
    installed = [path for path in target.iterdir() if path.is_dir()]
    assert len(installed) == 1
    assert (installed[0] / "SKILL.md").is_file()
    manifest_path = target / ".infinitas-skill-install-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    serialized = json.dumps(manifest, sort_keys=True)
    assert share["resolve_secret"] not in serialized
    assert "grant_" not in serialized

    revoked = client.post(f"/api/v1/share-links/{share['id']}/revoke", headers=headers)
    assert revoked.status_code == 200
    with pytest.raises(HostedShareError, match="HTTP 410"):
        run_install_from_share(
            root=temp_repo_copy,
            resolve_url=share["resolve_url"],
            target_dir=str(tmp_path / "revoked-install"),
            secret_env="TEST_SHARE_SECRET",
        )
