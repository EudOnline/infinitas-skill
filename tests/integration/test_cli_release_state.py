from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_NAME = "operate-infinitas-skill"
MODE = "local-preflight"


def _cli_env() -> dict[str, str]:
    return dict(os.environ, PYTHONPATH=str(ROOT / "src"))


def _run_release_state(
    command: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, env=env)
    assert result.returncode in {0, 1}, (
        f"command {command!r} exited {result.returncode}, expected 0 or 1\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return result


def _run_release_probe(
    args: list[str], probe_modules: list[str]
) -> subprocess.CompletedProcess[str]:
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
    return subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, text=True, capture_output=True, env=env
    )


def _load_payload(result: subprocess.CompletedProcess[str], label: str) -> dict:
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        raise AssertionError(
            f"{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        ) from exc


def assert_release_state_returns_expected_json() -> None:
    cli = _run_release_state(
        [
            sys.executable,
            "-m",
            "infinitas_skill.cli.main",
            "release",
            "check-state",
            SKILL_NAME,
            "--mode",
            MODE,
            "--json",
        ],
        env=_cli_env(),
    )
    cli_payload = _load_payload(cli, "infinitas CLI")
    assert cli_payload.get("mode") == MODE
    assert isinstance(cli_payload.get("release_ready"), bool)
    assert (cli_payload.get("skill") or {}).get("name") == SKILL_NAME
    assert ((cli_payload.get("git") or {}).get("expected_tag")) == f"skill/{SKILL_NAME}/v0.1.1"


def assert_release_cli_help_lists_maintained_subcommands() -> None:
    cli = _run_release_state(
        [
            sys.executable,
            "-m",
            "infinitas_skill.cli.main",
            "release",
            "--help",
        ],
        env=_cli_env(),
    )
    help_text = cli.stdout + cli.stderr
    for command in ["check-state", "signing-readiness", "doctor-signing", "bootstrap-signing"]:
        assert command in help_text, f"expected {command!r} in infinitas release help"


def assert_release_signing_readiness_returns_expected_json() -> None:
    cli = _run_release_state(
        [
            sys.executable,
            "-m",
            "infinitas_skill.cli.main",
            "release",
            "signing-readiness",
            "--skill",
            SKILL_NAME,
            "--json",
        ],
        env=_cli_env(),
    )
    cli_payload = _load_payload(cli, "infinitas release signing-readiness")
    assert cli_payload.get("overall_status") in {"ok", "warn", "fail"}
    assert isinstance(cli_payload.get("skills"), list)
    assert (cli_payload.get("skills") or [{}])[0].get("name") == SKILL_NAME


def assert_release_doctor_signing_returns_expected_json() -> None:
    cli = _run_release_state(
        [
            sys.executable,
            "-m",
            "infinitas_skill.cli.main",
            "release",
            "doctor-signing",
            SKILL_NAME,
            "--json",
        ],
        env=_cli_env(),
    )
    cli_payload = _load_payload(cli, "infinitas release doctor-signing")
    assert cli_payload.get("overall_status") in {"ok", "warn", "fail"}
    assert isinstance(cli_payload.get("checks"), list)
    assert cli_payload.get("skill") in {f"skills/active/{SKILL_NAME}", None}


def assert_release_bootstrap_signing_help_is_available() -> None:
    cli = _run_release_state(
        [
            sys.executable,
            "-m",
            "infinitas_skill.cli.main",
            "release",
            "bootstrap-signing",
            "--help",
        ],
        env=_cli_env(),
    )
    help_text = cli.stdout + cli.stderr
    for command in ["init-key", "add-allowed-signer", "configure-git", "authorize-publisher"]:
        assert command in help_text, f"expected {command!r} in bootstrap-signing help"


def assert_release_state_routes_through_package_modules() -> None:
    probe = _run_release_probe(
        ["release", "check-state", SKILL_NAME, "--mode", MODE, "--json"],
        [
            "policy_trace_lib",
            "infinitas_skill.release.service",
            "infinitas_skill.release.formatting",
            "infinitas_skill.release.git_state",
            "infinitas_skill.release.policy_state",
            "infinitas_skill.release.platform_state",
            "infinitas_skill.release.attestation_state",
        ],
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
    for module_name in [
        "infinitas_skill.release.service",
        "infinitas_skill.release.formatting",
        "infinitas_skill.release.git_state",
        "infinitas_skill.release.policy_state",
        "infinitas_skill.release.platform_state",
        "infinitas_skill.release.attestation_state",
    ]:
        assert modules.get(module_name), f"release CLI did not route through {module_name}"


def assert_release_signing_commands_route_through_package_modules() -> None:
    probe = _run_release_probe(
        ["release", "doctor-signing", SKILL_NAME, "--json"],
        [
            "signing_bootstrap_lib",
            "provenance_payload_lib",
            "infinitas_skill.release.signing_doctor",
            "infinitas_skill.release.signing_bootstrap",
            "infinitas_skill.release.attestation",
        ],
    )
    assert probe.returncode == 0, (
        f"release signing ownership probe failed\nstdout:\n{probe.stdout}\nstderr:\n{probe.stderr}"
    )
    probe_payload = _load_payload(probe, "release signing ownership probe")
    assert probe_payload.get("returncode") in {0, 1}, (
        f"release signing ownership probe command returned {probe_payload.get('returncode')}, expected 0 or 1\n"
        f"stdout:\n{probe_payload.get('stdout')}\n"
        f"stderr:\n{probe_payload.get('stderr')}"
    )
    modules = probe_payload.get("modules") or {}
    for legacy_module in ["signing_bootstrap_lib", "provenance_payload_lib"]:
        assert not modules.get(legacy_module), (
            f"release signing CLI still imports legacy {legacy_module} directly from scripts/"
        )
    for module_name in [
        "infinitas_skill.release.signing_doctor",
        "infinitas_skill.release.signing_bootstrap",
        "infinitas_skill.release.attestation",
    ]:
        assert modules.get(module_name), f"release signing CLI did not route through {module_name}"


def test_release_check_state_cli_returns_expected_json() -> None:
    assert_release_state_returns_expected_json()


def test_release_cli_help_lists_maintained_subcommands() -> None:
    assert_release_cli_help_lists_maintained_subcommands()


def test_release_check_state_cli_routes_through_package_modules() -> None:
    assert_release_state_routes_through_package_modules()


def test_release_signing_readiness_returns_expected_json() -> None:
    assert_release_signing_readiness_returns_expected_json()


def test_release_doctor_signing_returns_expected_json() -> None:
    assert_release_doctor_signing_returns_expected_json()


def test_release_bootstrap_signing_help_is_available() -> None:
    assert_release_bootstrap_signing_help_is_available()


def test_release_signing_commands_route_through_package_modules() -> None:
    assert_release_signing_commands_route_through_package_modules()


def main() -> None:
    assert_release_state_returns_expected_json()
    assert_release_cli_help_lists_maintained_subcommands()
    assert_release_state_routes_through_package_modules()
    assert_release_signing_readiness_returns_expected_json()
    assert_release_doctor_signing_returns_expected_json()
    assert_release_bootstrap_signing_help_is_available()
    assert_release_signing_commands_route_through_package_modules()
