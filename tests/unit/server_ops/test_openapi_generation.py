from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "generate-openapi.py"


def _run_generator(output_path: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        INFINITAS_SERVER_ENV="production",
        INFINITAS_SERVER_SECRET_KEY="short-hostile-secret",
        INFINITAS_SERVER_DATABASE_URL=f"sqlite:///{output_path.parent / 'must-not-exist.db'}",
        INFINITAS_SERVER_BOOTSTRAP_USERS="not-json",
        INFINITAS_SERVER_ALLOWED_HOSTS="not-json",
        PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "src")]),
    )
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(output_path), *extra_args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_generator_ignores_hostile_server_environment_and_avoids_database(tmp_path: Path) -> None:
    output_path = tmp_path / "openapi.json"

    result = _run_generator(output_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "/api/v1/access/me" in payload["paths"]
    assert not (tmp_path / "must-not-exist.db").exists()


def test_import_and_app_construction_do_not_create_database(tmp_path: Path) -> None:
    database_path = tmp_path / "must-not-exist.db"
    env = os.environ.copy()
    env.update(
        INFINITAS_SERVER_ENV="test",
        INFINITAS_SERVER_SECRET_KEY="test-secret-key",
        INFINITAS_SERVER_DATABASE_URL=f"sqlite:///{database_path}",
        INFINITAS_SERVER_BOOTSTRAP_USERS="[]",
        PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "src")]),
    )
    result = subprocess.run(
        [sys.executable, "-c", "import server.app; server.app.create_app()"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert not database_path.exists()


def test_check_reports_drift_without_writing(tmp_path: Path) -> None:
    output_path = tmp_path / "openapi.json"
    output_path.write_text('{"stale": true}\n', encoding="utf-8")

    result = _run_generator(output_path, "--check")

    assert result.returncode == 1
    assert output_path.read_text(encoding="utf-8") == '{"stale": true}\n'


def test_check_passes_for_current_schema(tmp_path: Path) -> None:
    output_path = tmp_path / "openapi.json"
    generated = _run_generator(output_path)
    assert generated.returncode == 0, generated.stderr

    checked = _run_generator(output_path, "--check")

    assert checked.returncode == 0, checked.stderr
