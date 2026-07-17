"""Canonical CLI runner for pytest tests.

Replaces the copy-pasted ``run_cli``/``run`` helpers found in ~60 shadow
``scripts/test-*.py`` files. Thin by design: it captures the subprocess result
and optionally checks the exit code; all behavioral assertions live in the test.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Ensure subprocess CLI invocations use the project venv even when this helper
# is imported by a test launched with a system Python interpreter.
_VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"
if _VENV_PYTHON.exists() and sys.executable != str(_VENV_PYTHON):
    sys.executable = str(_VENV_PYTHON)


@dataclass
class CliResult:
    """Captured output of a ``infinitas`` CLI invocation."""

    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def json(self) -> object:
        """Parse stdout as JSON, raising an AssertionError with full context on failure."""
        try:
            return json.loads(self.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"stdout was not valid JSON ({exc})\nstdout:\n{self.stdout}\nstderr:\n{self.stderr}"
            ) from exc


def run_cli(
    repo: Path,
    args: list[str],
    *,
    env: dict[str, str],
    expect: int | None = 0,
) -> CliResult:
    """Run ``infinitas <args>`` inside *repo* and return the captured result.

    When *expect* is not None the return code is checked here (mirrors the old
    ``run()`` helper) and a helpful AssertionError is raised on mismatch so the
    test sees both streams. Pass ``expect=None`` to assert on the code yourself.
    """
    command = [sys.executable, "-m", "infinitas_skill.cli.main", *args]
    completed = subprocess.run(
        command,
        cwd=repo,
        text=True,
        capture_output=True,
        env=env,
    )
    result = CliResult(completed.returncode, completed.stdout, completed.stderr)
    if expect is not None and completed.returncode != expect:
        raise AssertionError(
            f"command {args!r} exited {completed.returncode}, expected {expect}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return result
