from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _test_env() -> dict[str, str]:
    env = os.environ.copy()
    env["INFINITAS_SKIP_RELEASE_TESTS"] = "1"
    env["INFINITAS_SKIP_ATTESTATION_TESTS"] = "1"
    env["INFINITAS_SKIP_DISTRIBUTION_TESTS"] = "1"
    env["INFINITAS_SKIP_BOOTSTRAP_TESTS"] = "1"
    env["INFINITAS_SKIP_AI_WRAPPER_TESTS"] = "1"
    env["INFINITAS_SKIP_COMPAT_PIPELINE_TESTS"] = "1"
    env["INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS"] = "1"
    return env


def _run_script(path: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / path), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=_test_env(),
    )


def test_transparency_log_script_accepts_named_scenario() -> None:
    # This smoke scenario verifies selector plumbing only; real release-flow
    # transparency scenarios are covered separately because they are much heavier.
    result = _run_script(
        "scripts/test-transparency-log.py",
        "scenario_selector_smoke_test",
    )
    assert result.returncode == 0, result.stderr
    assert "OK: transparency log checks passed" in result.stdout


def test_release_invariants_script_accepts_named_scenario() -> None:
    result = _run_script(
        "scripts/test-release-invariants.py",
        "scenario_missing_signers_blocks_tag_creation",
    )
    assert result.returncode == 0, result.stderr
    assert "OK: release invariant checks passed" in result.stdout


def test_long_release_scripts_reject_unknown_scenarios() -> None:
    for path in [
        "scripts/test-transparency-log.py",
        "scripts/test-release-invariants.py",
    ]:
        result = _run_script(path, "not_a_real_scenario")
        combined = result.stdout + result.stderr
        assert result.returncode != 0
        assert "unknown scenario" in combined
