from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _run_cli(
    args: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    cli_env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    if env:
        cli_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "infinitas_skill.cli.main", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=cli_env,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_skill_fixture(root: Path) -> Path:
    skill_dir = root / "skill"
    _write_text(skill_dir / "BODY.md", "OpenClaw runtime fixture.\n")
    _write_json(
        skill_dir / "skill.json",
        {
            "schema_version": 1,
            "name": "openclaw-cli-fixture",
            "summary": "OpenClaw CLI fixture",
            "description": "Fixture for CLI validation",
            "instructions_body": "BODY.md",
            "tool_intents": {
                "required": ["shell_execution", "file_read"],
                "optional": [],
            },
            "verification": {
                "required_runtimes": ["openclaw"],
            },
            "openclaw_runtime": {
                "workspace_scope": "workspace",
                "plugin_capabilities": {"tools": ["shell"], "channels": ["chat"]},
            },
        },
    )
    return skill_dir


def test_infinitas_openclaw_profile_outputs_canonical_runtime_contract() -> None:
    result = _run_cli(["openclaw", "profile", "--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["platform"] == "openclaw"
    assert payload["capabilities"]["supports_subagents"] is True
    assert payload["skill_dir_candidates"][:2] == ["skills", ".agents/skills"]


def test_infinitas_openclaw_workspace_resolve_emits_candidate_paths(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    result = _run_cli(
        [
            "openclaw",
            "workspace",
            "resolve",
            str(workspace_root),
            "--home",
            str(fake_home),
            "--json",
        ]
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["workspace_root"] == str(workspace_root.resolve())
    assert payload["skill_dirs"] == [
        str((workspace_root / "skills").resolve()),
        str((workspace_root / ".agents" / "skills").resolve()),
        str((fake_home / ".agents" / "skills").resolve()),
        str((fake_home / ".openclaw" / "skills").resolve()),
    ]


def test_infinitas_openclaw_skill_validate_returns_contract_payload(tmp_path: Path) -> None:
    skill_dir = _make_skill_fixture(tmp_path)

    result = _run_cli(["openclaw", "skill", "validate", str(skill_dir), "--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["contract"]["platform"] == "openclaw"
    assert payload["contract"]["source_mode"] == "canonical"
    assert payload["contract"]["runtime"]["plugin_capabilities"] == {
        "tools": ["shell"],
        "channels": ["chat"],
    }
    assert payload["contract"]["verification"]["required_runtimes"] == ["openclaw"]
    assert payload["contract"]["verification"]["legacy"] == {
        "required_platforms": ["openclaw"],
        "required_platforms_deprecated": False,
    }


def test_infinitas_openclaw_plugin_inspect_normalizes_capabilities(tmp_path: Path) -> None:
    plugin_path = tmp_path / "openclaw.plugin.json"
    _write_json(
        plugin_path,
        {
            "name": "demo-plugin",
            "plugin_capabilities": {
                "tools": ["shell", "edit"],
                "channels": ["chat"],
                "ignored_flag": True,
            },
        },
    )

    result = _run_cli(["openclaw", "plugin", "inspect", str(plugin_path), "--json"])

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["path"] == str(plugin_path.resolve())
    assert payload["plugin_capabilities"] == {
        "tools": ["shell", "edit"],
        "channels": ["chat"],
    }
