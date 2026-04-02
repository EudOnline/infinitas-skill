"""Shared environment helpers for regression scripts."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

_PYTHON_ENV_PROBE = "from alembic import command; import pytest"
DEFAULT_SKIP_TEST_FLAGS = (
    "INFINITAS_SKIP_RELEASE_TESTS",
    "INFINITAS_SKIP_ATTESTATION_TESTS",
    "INFINITAS_SKIP_DISTRIBUTION_TESTS",
    "INFINITAS_SKIP_BOOTSTRAP_TESTS",
    "INFINITAS_SKIP_AI_WRAPPER_TESTS",
    "INFINITAS_SKIP_COMPAT_PIPELINE_TESTS",
    "INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS",
)
DEFAULT_REQUIRE_TEST_FLAGS = (
    "INFINITAS_REQUIRE_BROWSER_RUNTIME_TESTS",
    "INFINITAS_REQUIRE_PRIVATE_REGISTRY_TESTS",
    "INFINITAS_REQUIRE_HOSTED_E2E_TESTS",
)
DEFAULT_RELEASE_HELPER_CHECK_ALL_BLOCKS = "focused-integration"


def preferred_python_bin_dir(
    root: Path, *, probe_command: str = _PYTHON_ENV_PROBE
) -> Path | None:
    candidates = [Path(sys.executable), root / ".venv" / "bin" / "python3"]
    seen = set()
    probe_cwd = Path(tempfile.gettempdir())
    for candidate in candidates:
        candidate = Path(candidate).expanduser()
        marker = str(candidate)
        if marker in seen or not candidate.exists():
            continue
        seen.add(marker)
        result = subprocess.run(
            [str(candidate), "-c", probe_command],
            cwd=probe_cwd,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return candidate.parent
    return None


def prepend_preferred_python_bin_to_path(
    env: dict[str, str], *, root: Path, probe_command: str = _PYTHON_ENV_PROBE
) -> dict[str, str]:
    python_bin = preferred_python_bin_dir(root, probe_command=probe_command)
    if python_bin is None:
        return env
    current_path = env.get("PATH")
    env["PATH"] = f"{python_bin}:{current_path}" if current_path else str(python_bin)
    return env


def build_regression_test_env(
    root: Path,
    *,
    extra: dict[str, str] | None = None,
    env: dict[str, str] | None = None,
    add_pythonpath: str | Path | None = None,
    skip_test_flags: tuple[str, ...] = DEFAULT_SKIP_TEST_FLAGS,
    require_test_flags: tuple[str, ...] = DEFAULT_REQUIRE_TEST_FLAGS,
) -> dict[str, str]:
    resolved_env = dict(os.environ if env is None else env)
    for key in require_test_flags:
        resolved_env.pop(key, None)
    for key in skip_test_flags:
        resolved_env[key] = "1"
    resolved_env.setdefault(
        "INFINITAS_RELEASE_HELPER_CHECK_ALL_BLOCKS",
        DEFAULT_RELEASE_HELPER_CHECK_ALL_BLOCKS,
    )
    if add_pythonpath is not None:
        pythonpath = str(Path(add_pythonpath))
        current_pythonpath = resolved_env.get("PYTHONPATH")
        resolved_env["PYTHONPATH"] = (
            f"{pythonpath}:{current_pythonpath}" if current_pythonpath else pythonpath
        )
    prepend_preferred_python_bin_to_path(resolved_env, root=root)
    if extra:
        resolved_env.update(extra)
    return resolved_env


__all__ = [
    "DEFAULT_REQUIRE_TEST_FLAGS",
    "DEFAULT_RELEASE_HELPER_CHECK_ALL_BLOCKS",
    "DEFAULT_SKIP_TEST_FLAGS",
    "build_regression_test_env",
    "prepend_preferred_python_bin_to_path",
    "preferred_python_bin_dir",
]
