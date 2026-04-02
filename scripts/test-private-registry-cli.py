#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def cli_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    return env


def registry_cli(root: Path, *args: str) -> list[str]:
    return [sys.executable, "-m", "infinitas_skill.cli.main", "registry", *args]


def run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=cli_env(ROOT))
    if result.returncode != 0:
        fail(
            f"command {command!r} failed with {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result.stdout + result.stderr


def run_result(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=cli_env(ROOT))


def scenario_private_first_cli_surface() -> None:
    cli_help = run(registry_cli(ROOT, "--help"))
    for noun in ["skills", "drafts", "releases", "exposures", "grants", "tokens", "reviews"]:
        if noun not in cli_help:
            fail(f"expected {noun!r} in top-level cli help")
    if "submissions" in cli_help:
        fail("expected submissions to disappear from top-level cli help")

    drafts_help = run(registry_cli(ROOT, "drafts", "--help"))
    if "create" not in drafts_help or "seal" not in drafts_help:
        fail("expected drafts help to expose create and seal")
    if "drafts create" not in cli_help and "drafts" not in drafts_help:
        fail("expected drafts vocabulary to be visible in cli help")

    removed_legacy = run_result(registry_cli(ROOT, "submissions", "--help"))
    if removed_legacy.returncode != 2 or "invalid choice" not in removed_legacy.stderr:
        fail(
            "expected submissions command to be removed entirely, "
            f"got returncode={removed_legacy.returncode} stdout={removed_legacy.stdout!r} stderr={removed_legacy.stderr!r}"
        )


def main() -> None:
    scenario_private_first_cli_surface()
    print("OK: private registry cli checks passed")


if __name__ == "__main__":
    main()
