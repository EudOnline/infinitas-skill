from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from tests.fixtures.repo_state import create_repo_state
from test_support.server_ops import HealthServer, run_command as shared_run_command


ROOT = Path(__file__).resolve().parents[2]


def _run(command: list[str], *, cwd: Path = ROOT, expect: int | None = 0, env: dict[str, str] | None = None):
    try:
        return shared_run_command(command, cwd=cwd, expect=expect, env=env)
    except SystemExit as exc:
        raise AssertionError(str(exc).removeprefix("FAIL: ")) from exc


def _run_cli(args: list[str], *, expect: int | None = 0, env: dict[str, str] | None = None):
    merged_env = os.environ.copy()
    if env is not None:
        merged_env.update(env)
    existing_pythonpath = merged_env.get("PYTHONPATH", "")
    merged_env["PYTHONPATH"] = (
        f"{ROOT / 'src'}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(ROOT / "src")
    )
    return _run(["infinitas", *args], expect=expect, env=merged_env)


def _run_legacy(script_name: str, args: list[str], *, expect: int | None = 0, env: dict[str, str] | None = None):
    return _run([sys.executable, str(ROOT / "scripts" / script_name), *args], expect=expect, env=env)


def _load_json_output(result, *, label: str) -> dict:
    try:
        return json.loads(result.stdout)
    except Exception as exc:
        raise AssertionError(
            f"{label} did not emit JSON output: {exc}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        ) from exc


def assert_server_cli_help_lists_maintained_subcommands() -> None:
    result = _run_cli(["server", "--help"], expect=0)
    help_text = result.stdout + result.stderr
    for command in ["healthcheck", "backup", "render-systemd", "prune-backups", "worker", "inspect-state"]:
        assert command in help_text, f"expected {command!r} in infinitas server help"


def assert_server_ops_split_into_modules() -> None:
    from infinitas_skill.server import ops

    ops_path = ROOT / "src" / "infinitas_skill" / "server" / "ops.py"
    line_count = len(ops_path.read_text(encoding="utf-8").splitlines())
    assert line_count <= 650, (
        f"expected src/infinitas_skill/server/ops.py to stay within 650 lines after extraction, got {line_count}"
    )
    assert ops.run_server_healthcheck.__module__ == "infinitas_skill.server.health"
    assert ops.run_server_prune_backups.__module__ == "infinitas_skill.server.backup"


def assert_server_healthcheck_matches_legacy() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-cli-server-health-"))
    try:
        repo_state = create_repo_state(tmpdir)
        with HealthServer() as base_url:
            args = [
                "--api-url",
                base_url,
                "--repo-path",
                str(repo_state.repo),
                "--artifact-path",
                str(repo_state.artifact_dir),
                "--database-url",
                f"sqlite:///{repo_state.db_path}",
                "--json",
            ]
            cli = _run_cli(["server", "healthcheck", *args], expect=0)
            legacy = _run_legacy("server-healthcheck.py", args, expect=0)

        cli_payload = _load_json_output(cli, label="infinitas server healthcheck")
        legacy_payload = _load_json_output(legacy, label="legacy server-healthcheck.py")
        assert cli_payload == legacy_payload, (
            f"healthcheck payload mismatch\ncli:\n{cli.stdout}\nlegacy:\n{legacy.stdout}"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_server_cli_help_lists_maintained_subcommands() -> None:
    assert_server_cli_help_lists_maintained_subcommands()


def test_server_ops_split_into_smaller_modules() -> None:
    assert_server_ops_split_into_modules()


def test_server_healthcheck_matches_legacy_script() -> None:
    assert_server_healthcheck_matches_legacy()


def main() -> None:
    assert_server_cli_help_lists_maintained_subcommands()
    assert_server_ops_split_into_modules()
    assert_server_healthcheck_matches_legacy()
