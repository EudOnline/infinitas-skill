from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPENCLAW_RUNTIME = {
    "platform": "openclaw",
    "source_mode": "legacy",
    "workspace_scope": "workspace",
    "workspace_targets": ["skills", ".agents/skills", "~/.agents/skills", "~/.openclaw/skills"],
    "skill_precedence": [
        "skills",
        ".agents/skills",
        "~/.agents/skills",
        "~/.openclaw/skills",
        "bundled",
        "extra",
    ],
    "install_targets": {
        "workspace": ["skills", ".agents/skills"],
        "shared": ["~/.agents/skills", "~/.openclaw/skills"],
    },
    "requires": {"tools": [], "bins": [], "env": [], "config": []},
    "plugin_capabilities": {},
    "background_tasks": {"required": False},
    "subagents": {"required": False},
    "legacy_compatibility": {
        "agent_compatible": ["openclaw", "claude-code", "codex"],
        "agent_compatible_deprecated": True,
    },
    "readiness": {
        "ready": True,
        "supports_background_tasks": True,
        "supports_plugins": True,
        "supports_subagents": True,
        "status": "ready",
    },
}


def _run(
    command: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env)


def _prepare_repo() -> tuple[Path, Path]:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-cli-install-workflows-"))
    repo = tmpdir / "repo"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(
            ".git",
            ".planning",
            "__pycache__",
            ".cache",
            "scripts/__pycache__",
            ".worktrees",
            ".venv",
        ),
    )
    return tmpdir, repo


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _cli_env(repo: Path) -> dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(repo / "src"))


def _run_cli(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return _run(
        [sys.executable, "-m", "infinitas_skill.cli.main", *args],
        cwd=repo,
        env=_cli_env(repo),
    )


def _discovery_index_payload() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-03-12T00:00:00Z",
        "default_registry": "self",
        "sources": [
            {
                "name": "self",
                "kind": "git",
                "priority": 100,
                "trust_level": "private",
                "root": "/tmp/self",
                "status": "ready",
            },
            {
                "name": "external-demo",
                "kind": "local",
                "priority": 50,
                "trust_level": "trusted",
                "root": "/tmp/external-demo",
                "status": "ready",
            },
        ],
        "resolution_policy": {
            "private_registry_first": True,
            "external_requires_confirmation": True,
            "auto_install_mutable_sources": False,
        },
        "skills": [
            {
                "name": "demo-skill",
                "qualified_name": "lvxiaoer/demo-skill",
                "publisher": "lvxiaoer",
                "summary": "Private demo skill",
                "source_registry": "self",
                "source_priority": 100,
                "match_names": ["demo-skill", "lvxiaoer/demo-skill"],
                "default_install_version": "1.2.3",
                "latest_version": "1.2.3",
                "available_versions": ["1.2.3"],
                "agent_compatible": ["openclaw", "claude-code", "codex"],
                "install_requires_confirmation": False,
                "trust_level": "private",
                "trust_state": "verified",
                "tags": ["private", "demo"],
                "maturity": "stable",
                "quality_score": 90,
                "last_verified_at": "2026-03-14T00:00:00Z",
                "capabilities": ["demo", "private-registry"],
                "verified_support": {},
                "attestation_formats": ["ssh"],
                "use_when": ["Need private demo skill"],
                "avoid_when": [],
                "runtime_assumptions": [],
            },
            {
                "name": "external-only-skill",
                "qualified_name": "partner/external-only-skill",
                "publisher": "partner",
                "summary": "External only skill",
                "source_registry": "external-demo",
                "source_priority": 50,
                "match_names": ["external-only-skill", "partner/external-only-skill"],
                "default_install_version": "0.9.0",
                "latest_version": "0.9.0",
                "available_versions": ["0.9.0"],
                "agent_compatible": ["openclaw", "claude-code", "codex"],
                "install_requires_confirmation": True,
                "trust_level": "trusted",
                "trust_state": "attested",
                "tags": ["external", "demo"],
                "maturity": "beta",
                "quality_score": 67,
                "last_verified_at": "2026-03-13T00:00:00Z",
                "capabilities": ["external-coverage"],
                "verified_support": {},
                "attestation_formats": ["ssh"],
                "use_when": ["Need external coverage"],
                "avoid_when": [],
                "runtime_assumptions": [],
            },
        ],
    }


def _ai_index_payload() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-03-12T00:00:00Z",
        "registry": {"default_registry": "self"},
        "install_policy": {
            "mode": "immutable-only",
            "direct_source_install_allowed": False,
            "require_attestation": True,
            "require_sha256": True,
        },
        "skills": [
            {
                "name": "demo-skill",
                "publisher": "lvxiaoer",
                "qualified_name": "lvxiaoer/demo-skill",
                "summary": "Private demo skill",
                "tags": ["private", "demo"],
                "use_when": ["Need private demo skill"],
                "avoid_when": [],
                "runtime_assumptions": [],
                "agent_compatible": ["openclaw", "claude-code", "codex"],
                "maturity": "stable",
                "quality_score": 90,
                "last_verified_at": "2026-03-14T00:00:00Z",
                "capabilities": ["demo", "private-registry"],
                "verified_support": {},
                "trust_state": "verified",
                "runtime": OPENCLAW_RUNTIME,
                "default_install_version": "1.2.3",
                "latest_version": "1.2.3",
                "available_versions": ["1.2.3"],
                "entrypoints": {
                    "skill_md": "skills/active/demo-skill/SKILL.md",
                },
                "requires": {"tools": [], "env": []},
                "versions": {
                    "1.2.3": {
                        "manifest_path": (
                            "catalog/distributions/_legacy/demo-skill/1.2.3/manifest.json"
                        ),
                        "distribution_manifest_path": (
                            "catalog/distributions/_legacy/demo-skill/1.2.3/manifest.json"
                        ),
                        "bundle_path": (
                            "catalog/distributions/_legacy/demo-skill/1.2.3/bundle.tar.gz"
                        ),
                        "bundle_sha256": "deadbeef",
                        "attestation_path": "catalog/provenance/demo-skill-1.2.3.json",
                        "attestation_signature_path": None,
                        "published_at": "2026-03-12T00:00:00Z",
                        "stability": "stable",
                        "installable": True,
                        "attestation_formats": ["ssh"],
                        "trust_state": "verified",
                        "resolution": {
                            "preferred_source": "distribution-manifest",
                            "fallback_allowed": False,
                        },
                    }
                },
            },
            {
                "name": "external-only-skill",
                "publisher": "partner",
                "qualified_name": "partner/external-only-skill",
                "summary": "External only skill",
                "tags": ["external", "demo"],
                "use_when": ["Need external coverage"],
                "avoid_when": [],
                "runtime_assumptions": [],
                "agent_compatible": ["openclaw", "claude-code", "codex"],
                "maturity": "beta",
                "quality_score": 67,
                "last_verified_at": "2026-03-13T00:00:00Z",
                "capabilities": ["external-coverage"],
                "verified_support": {},
                "trust_state": "attested",
                "runtime": OPENCLAW_RUNTIME,
                "default_install_version": "0.9.0",
                "latest_version": "0.9.0",
                "available_versions": ["0.9.0"],
                "entrypoints": {
                    "skill_md": "skills/active/external-only-skill/SKILL.md",
                },
                "requires": {"tools": [], "env": []},
                "versions": {
                    "0.9.0": {
                        "manifest_path": (
                            "catalog/distributions/_legacy/"
                            "external-only-skill/0.9.0/manifest.json"
                        ),
                        "distribution_manifest_path": (
                            "catalog/distributions/_legacy/"
                            "external-only-skill/0.9.0/manifest.json"
                        ),
                        "bundle_path": (
                            "catalog/distributions/_legacy/"
                            "external-only-skill/0.9.0/bundle.tar.gz"
                        ),
                        "bundle_sha256": "deadbeef",
                        "attestation_path": "catalog/provenance/external-only-skill-0.9.0.json",
                        "attestation_signature_path": None,
                        "published_at": "2026-03-12T00:00:00Z",
                        "stability": "stable",
                        "installable": True,
                        "attestation_formats": ["ssh"],
                        "trust_state": "attested",
                        "resolution": {
                            "preferred_source": "distribution-manifest",
                            "fallback_allowed": False,
                        },
                    }
                },
            },
        ],
    }


def _configure_external_registry(repo: Path, tmpdir: Path) -> None:
    external_repo = tmpdir / "external-demo"
    _write_json(external_repo / "catalog" / "ai-index.json", _ai_index_payload())
    external_distribution_dir = (
        external_repo
        / "catalog"
        / "distributions"
        / "_legacy"
        / "external-only-skill"
        / "0.9.0"
    )
    external_distribution_dir.mkdir(parents=True, exist_ok=True)
    (external_repo / "catalog" / "provenance").mkdir(parents=True, exist_ok=True)
    (external_distribution_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
    (external_distribution_dir / "bundle.tar.gz").write_text("fixture\n", encoding="utf-8")
    (external_repo / "catalog" / "provenance" / "external-only-skill-0.9.0.json").write_text(
        "{}\n", encoding="utf-8"
    )

    registry_path = repo / "config" / "registry-sources.json"
    registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_payload["registries"].append(
        {
            "name": "external-demo",
            "kind": "local",
            "local_path": os.path.relpath(external_repo, repo),
            "priority": 50,
            "enabled": True,
            "trust": "trusted",
            "update_policy": {"mode": "local-only"},
            "notes": "External fixture registry for CLI install workflow tests",
        }
    )
    _write_json(registry_path, registry_payload)


def test_install_cli_exposes_resolve_and_by_name_workflows() -> None:
    tmpdir, repo = _prepare_repo()
    try:
        _write_json(repo / "catalog" / "discovery-index.json", _discovery_index_payload())
        _write_json(repo / "catalog" / "ai-index.json", _ai_index_payload())
        _configure_external_registry(repo, tmpdir)

        resolve = _run_cli(repo, ["install", "resolve-skill", "demo-skill", "--json"])
        assert resolve.returncode == 0, (
            f"resolve-skill CLI returned {resolve.returncode}\n"
            f"stdout:\n{resolve.stdout}\n"
            f"stderr:\n{resolve.stderr}"
        )
        resolve_payload = json.loads(resolve.stdout)
        assert resolve_payload["state"] == "resolved-private"
        assert resolve_payload["resolved"]["source_registry"] == "self"

        by_name = _run_cli(
            repo,
            [
                "install",
                "by-name",
                "external-only-skill",
                str(tmpdir / "target"),
                "--mode",
                "confirm",
                "--json",
            ],
        )
        assert by_name.returncode == 0, (
            f"install by-name CLI returned {by_name.returncode}\n"
            f"stdout:\n{by_name.stdout}\n"
            f"stderr:\n{by_name.stderr}"
        )
        install_payload = json.loads(by_name.stdout)
        assert install_payload["state"] == "planned"
        assert install_payload["requires_confirmation"] is True
        assert install_payload["qualified_name"] == "partner/external-only-skill"
    finally:
        shutil.rmtree(tmpdir)
