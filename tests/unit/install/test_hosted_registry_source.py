from __future__ import annotations

import json
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path
from urllib.request import Request

import pytest

from infinitas_skill.install.http_registry import (
    HostedRegistryError,
    _RedirectLimiter,
    build_registry_url,
)
from infinitas_skill.install.registry_source_primitives import resolve_registry_root
from infinitas_skill.install.registry_sources import (
    find_registry,
    registry_identity,
    validate_registry_config,
)
from infinitas_skill.install.service import plan_from_skill_dir
from infinitas_skill.install.source_resolver_cli import resolve_source_candidate

ROOT = Path(__file__).resolve().parents[3]


def _base_config() -> dict:
    return {
        "$schema": "../schemas/registry-sources.schema.json",
        "default_registry": "hosted",
        "registries": [
            {
                "name": "hosted",
                "kind": "http",
                "base_url": "https://skills.example.com/api/v1/registry",
                "enabled": True,
                "priority": 100,
                "trust": "private",
                "auth": {"mode": "token", "env": "INFINITAS_REGISTRY_TOKEN"},
            }
        ],
    }


def _errors(cfg: dict) -> list[str]:
    return validate_registry_config(ROOT, cfg)


def test_valid_http_registry_config() -> None:
    assert _errors(_base_config()) == []


def test_http_registry_requires_base_url() -> None:
    cfg = _base_config()
    cfg["registries"][0].pop("base_url")
    errors = _errors(cfg)
    assert errors and any("http registry 'hosted' missing non-empty base_url" in e for e in errors)


@pytest.mark.parametrize("trust", ["private", "trusted", "public"])
def test_http_registry_rejects_insecure_base_url_for_trusted_tiers(trust: str) -> None:
    cfg = _base_config()
    cfg["registries"][0]["trust"] = trust
    cfg["registries"][0]["base_url"] = "http://skills.example.com/api/v1/registry"
    errors = _errors(cfg)
    assert errors and any(
        f"registry 'hosted' with trust '{trust}' must use an https base_url" in e for e in errors
    )


def test_http_registry_rejects_invalid_auth_modes() -> None:
    cfg = _base_config()
    cfg["registries"][0]["auth"] = {"mode": "cookie"}
    errors = _errors(cfg)
    assert errors and any(
        "registry 'hosted' auth.mode must be one of ['none', 'token']" in e for e in errors
    )


def test_http_registry_identity_resolves_without_local_clone() -> None:
    cfg = _base_config()
    assert _errors(cfg) == []
    reg = find_registry(cfg, "hosted")
    assert reg is not None
    assert resolve_registry_root(ROOT, reg) is None

    identity = registry_identity(ROOT, reg)
    assert identity["registry_kind"] == "http"
    assert identity["registry_base_url"] == "https://skills.example.com/api/v1/registry"
    assert identity["registry_host"] == "skills.example.com"
    assert identity["registry_root"] is None
    assert identity.get("registry_commit") is None
    assert identity.get("registry_tag") is None


def test_registry_url_keeps_relative_paths_under_base_path() -> None:
    assert build_registry_url(
        "https://skills.example.com/api/v1/registry", "catalog/index.json"
    ) == ("https://skills.example.com/api/v1/registry/catalog/index.json")


@pytest.mark.parametrize("path", ["../internal", "catalog/../../internal", "https://evil.test/x"])
def test_registry_url_rejects_base_escape(path: str) -> None:
    with pytest.raises(HostedRegistryError):
        build_registry_url("https://skills.example.com/api/v1/registry", path)


def test_registry_redirect_rejects_cross_origin_and_preserves_same_origin_auth() -> None:
    request = Request(
        "https://skills.example.com/api/v1/registry/index.json",
        headers={"Authorization": "Bearer secret"},
    )
    handler = _RedirectLimiter(("https", "skills.example.com", None))
    redirected = handler.redirect_request(
        request,
        BytesIO(),
        302,
        "Found",
        HTTPMessage(),
        "https://skills.example.com/api/v1/registry/current.json",
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") == "Bearer secret"

    with pytest.raises(HostedRegistryError):
        handler.redirect_request(
            request,
            BytesIO(),
            302,
            "Found",
            HTTPMessage(),
            "https://evil.example/steal",
        )


def test_source_resolution_uses_explicit_consumer_root(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "registry-sources.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(_base_config()),
        encoding="utf-8",
    )
    monkeypatch.setenv("INFINITAS_REGISTRY_TOKEN", "consumer-token")
    monkeypatch.setattr(
        "infinitas_skill.install.source_resolver_cli.fetch_json",
        lambda base_url, path, token_env=None: {
            "skills": [
                {
                    "name": "hosted-skill",
                    "publisher": "team",
                    "qualified_name": "team/hosted-skill",
                    "latest_version": "1.0.0",
                    "default_install_version": "1.0.0",
                    "versions": {
                        "1.0.0": {
                            "manifest_path": "skills/team/hosted-skill/1.0.0/manifest.json",
                            "bundle_path": "skills/team/hosted-skill/1.0.0/skill.tar.gz",
                            "bundle_sha256": "abc123",
                            "attestation_path": "provenance/team--hosted-skill-1.0.0.json",
                            "attestation_signature_path": (
                                "provenance/team--hosted-skill-1.0.0.json.ssig"
                            ),
                        }
                    },
                }
            ]
        },
    )

    result = resolve_source_candidate(
        "team/hosted-skill",
        root=tmp_path,
        registry="hosted",
        version="1.0.0",
    )

    assert result["qualified_name"] == "team/hosted-skill"
    assert result["registry_name"] == "hosted"
    assert result["version"] == "1.0.0"


def test_dependency_planner_uses_synced_http_catalog_from_explicit_root(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "registry-sources.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(_base_config()), encoding="utf-8")
    distributions_path = (
        tmp_path / ".cache" / "registries" / "hosted" / "catalog" / "distributions.json"
    )
    distributions_path.parent.mkdir(parents=True)
    distributions_path.write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "name": "dependency-skill",
                        "publisher": "team",
                        "qualified_name": "team/dependency-skill",
                        "version": "1.0.0",
                        "status": "active",
                        "manifest_path": "skills/team/dependency-skill/1.0.0/manifest.json",
                        "bundle_path": "skills/team/dependency-skill/1.0.0/skill.tar.gz",
                        "bundle_sha256": "abc123",
                        "metadata": {"depends_on": [], "conflicts_with": []},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    skill_dir = tmp_path / "root-skill"
    skill_dir.mkdir()
    (skill_dir / "_meta.json").write_text(
        json.dumps(
            {
                "name": "root-skill",
                "publisher": "team",
                "qualified_name": "team/root-skill",
                "version": "1.0.0",
                "status": "active",
                "distribution": {"installable": True},
                "depends_on": [{"name": "team/dependency-skill", "version": "1.0.0"}],
                "conflicts_with": [],
            }
        ),
        encoding="utf-8",
    )

    plan = plan_from_skill_dir(
        skill_dir,
        root=tmp_path,
        source_registry="hosted",
        target_dir=tmp_path / "target",
    )

    assert plan["registries_consulted"] == ["hosted"]
    assert [step["qualified_name"] for step in plan["steps"]] == [
        "team/dependency-skill",
        "team/root-skill",
    ]
