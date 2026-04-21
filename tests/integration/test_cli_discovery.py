from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _cli_env() -> dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(ROOT / "src"))


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "infinitas_skill.cli.main", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=_cli_env(),
    )


def _load_json_output(result: subprocess.CompletedProcess[str], label: str) -> dict:
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        raise AssertionError(
            f"{label} did not emit JSON output: {exc}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        ) from exc


def test_discovery_cli_search_recommend_and_inspect_are_maintained_surfaces() -> None:
    search = _run_cli(["discovery", "search", "consume", "--json"])
    recommend = _run_cli(
        [
            "discovery",
            "recommend",
            "Need a released skill for repository operations",
            "--target-agent",
            "codex",
            "--json",
        ]
    )
    inspect = _run_cli(
        [
            "discovery",
            "inspect",
            "lvxiaoer/consume-infinitas-skill",
            "--json",
        ]
    )

    assert search.returncode == 0, search.stderr
    assert recommend.returncode == 0, recommend.stderr
    assert inspect.returncode == 0, inspect.stderr

    search_payload = _load_json_output(search, "discovery search")
    recommend_payload = _load_json_output(recommend, "discovery recommend")
    inspect_payload = _load_json_output(inspect, "discovery inspect")

    assert search_payload["ok"] is True
    assert search_payload["results"], "expected at least one search result"

    assert recommend_payload["ok"] is True
    assert recommend_payload["results"], "expected at least one ranked recommendation"

    assert inspect_payload["ok"] is True
    assert inspect_payload["runtime"]["platform"] == "openclaw"
    assert inspect_payload["distribution"]["manifest_path"]
