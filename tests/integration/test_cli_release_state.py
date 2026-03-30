from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_NAME = "operate-infinitas-skill"
MODE = "local-preflight"


def _run_release_state(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    assert result.returncode in {0, 1}, (
        f"command {command!r} exited {result.returncode}, expected 0 or 1\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return result


def _run_release_probe(args: list[str], probe_modules: list[str]) -> subprocess.CompletedProcess[str]:
    script = (
        "import contextlib, io, json, sys\n"
        "from infinitas_skill.cli.main import main\n"
        "stdout = io.StringIO()\n"
        "stderr = io.StringIO()\n"
        "with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):\n"
        f"    code = main({args!r})\n"
        f"payload = {{'returncode': code, 'stdout': stdout.getvalue(), 'stderr': stderr.getvalue(), 'modules': {{name: name in sys.modules for name in {probe_modules!r}}}}}\n"
        "print(json.dumps(payload))\n"
    )
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    return subprocess.run([sys.executable, "-c", script], cwd=ROOT, text=True, capture_output=True, env=env)


def _load_payload(result: subprocess.CompletedProcess[str], label: str) -> dict:
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        raise AssertionError(
            f"{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        ) from exc


def assert_release_state_matches_legacy_json() -> None:
    cli = _run_release_state(
        [
            "infinitas",
            "release",
            "check-state",
            SKILL_NAME,
            "--mode",
            MODE,
            "--json",
        ]
    )
    legacy = _run_release_state(
        [
            sys.executable,
            str(ROOT / "scripts" / "check-release-state.py"),
            SKILL_NAME,
            "--mode",
            MODE,
            "--json",
        ]
    )
    cli_payload = _load_payload(cli, "infinitas CLI")
    legacy_payload = _load_payload(legacy, "legacy check-release-state.py")

    assert cli.returncode == legacy.returncode
    for field in ["mode", "release_ready"]:
        assert cli_payload.get(field) == legacy_payload.get(field)

    assert (cli_payload.get("skill") or {}).get("name") == (legacy_payload.get("skill") or {}).get("name")
    assert ((cli_payload.get("git") or {}).get("expected_tag")) == (
        (legacy_payload.get("git") or {}).get("expected_tag")
    )


def assert_release_state_routes_through_package_modules() -> None:
    probe = _run_release_probe(
        ["release", "check-state", SKILL_NAME, "--mode", MODE, "--json"],
        ["policy_trace_lib", "infinitas_skill.release.service", "infinitas_skill.release.formatting"],
    )
    assert probe.returncode == 0, (
        f"release ownership probe failed\nstdout:\n{probe.stdout}\nstderr:\n{probe.stderr}"
    )
    probe_payload = _load_payload(probe, "release ownership probe")
    assert probe_payload.get("returncode") in {0, 1}, (
        f"release ownership probe command returned {probe_payload.get('returncode')}, expected 0 or 1\n"
        f"stdout:\n{probe_payload.get('stdout')}\n"
        f"stderr:\n{probe_payload.get('stderr')}"
    )
    modules = probe_payload.get("modules") or {}
    assert not modules.get("policy_trace_lib")
    for module_name in ["infinitas_skill.release.service", "infinitas_skill.release.formatting"]:
        assert modules.get(module_name), f"release CLI did not route through {module_name}"


def test_release_check_state_cli_matches_expected_json() -> None:
    assert_release_state_matches_legacy_json()


def test_release_check_state_cli_routes_through_package_modules() -> None:
    assert_release_state_routes_through_package_modules()


def main() -> None:
    assert_release_state_matches_legacy_json()
    assert_release_state_routes_through_package_modules()
