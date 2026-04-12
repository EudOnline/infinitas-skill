#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FIXTURE_BOOTSTRAP_USERS = [
    {
        "username": "fixture-maintainer",
        "display_name": "Fixture Maintainer",
        "role": "maintainer",
        "token": "fixture-maintainer-token",
    }
]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def assert_contains(text: str, needle: str, label: str) -> None:
    if needle not in text:
        fail(f"{label} did not include {needle!r}\n{text}")


def run_settings_probe(env: dict[str, str], *, expect: int = 0) -> subprocess.CompletedProcess[str]:
    probe = """
import json
from server.settings import get_settings

settings = get_settings()
print(json.dumps({
    "environment": settings.environment,
    "secret_key": settings.secret_key,
    "allowed_hosts": settings.allowed_hosts,
    "bootstrap_users": settings.bootstrap_users,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )
    if result.returncode != expect:
        fail(
            f"settings probe exited {result.returncode}, expected {expect}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def build_env(tmpdir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmpdir / 'server.db'}"
    env["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmpdir / "artifacts")
    env["INFINITAS_SERVER_REPO_PATH"] = str(ROOT)
    for key in [
        "INFINITAS_SERVER_ENV",
        "INFINITAS_SERVER_SECRET_KEY",
        "INFINITAS_SERVER_ALLOWED_HOSTS",
        "INFINITAS_SERVER_BOOTSTRAP_USERS",
        "INFINITAS_SERVER_ALLOW_INSECURE_DEFAULTS",
    ]:
        env.pop(key, None)
    return env


def scenario_production_requires_explicit_secret() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-settings-secret-"))
    try:
        env = build_env(tmpdir)
        env["INFINITAS_SERVER_ENV"] = "production"
        env["INFINITAS_SERVER_ALLOWED_HOSTS"] = json.dumps(["registry.example.com"])
        env["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(FIXTURE_BOOTSTRAP_USERS)

        missing_secret = run_settings_probe(env, expect=1)
        assert_contains(
            missing_secret.stderr + missing_secret.stdout,
            "INFINITAS_SERVER_SECRET_KEY",
            "missing production secret failure",
        )

        env["INFINITAS_SERVER_SECRET_KEY"] = "change-me"
        default_secret = run_settings_probe(env, expect=1)
        assert_contains(
            default_secret.stderr + default_secret.stdout,
            "INFINITAS_SERVER_SECRET_KEY",
            "default production secret failure",
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_production_requires_explicit_bootstrap_users() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-settings-bootstrap-"))
    try:
        env = build_env(tmpdir)
        env["INFINITAS_SERVER_ENV"] = "production"
        env["INFINITAS_SERVER_SECRET_KEY"] = "prod-secret-key"
        env["INFINITAS_SERVER_ALLOWED_HOSTS"] = json.dumps(["registry.example.com"])

        missing_bootstrap = run_settings_probe(env, expect=1)
        assert_contains(
            missing_bootstrap.stderr + missing_bootstrap.stdout,
            "INFINITAS_SERVER_BOOTSTRAP_USERS",
            "missing production bootstrap failure",
        )

        env["INFINITAS_SERVER_BOOTSTRAP_USERS"] = "[]"
        empty_bootstrap = run_settings_probe(env, expect=1)
        assert_contains(
            empty_bootstrap.stderr + empty_bootstrap.stdout,
            "INFINITAS_SERVER_BOOTSTRAP_USERS",
            "empty production bootstrap failure",
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_production_requires_explicit_allowed_hosts() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-settings-hosts-"))
    try:
        env = build_env(tmpdir)
        env["INFINITAS_SERVER_ENV"] = "production"
        env["INFINITAS_SERVER_SECRET_KEY"] = "prod-secret-key"
        env["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(FIXTURE_BOOTSTRAP_USERS)

        missing_hosts = run_settings_probe(env, expect=1)
        assert_contains(
            missing_hosts.stderr + missing_hosts.stdout,
            "INFINITAS_SERVER_ALLOWED_HOSTS",
            "missing production allowed hosts failure",
        )

        env["INFINITAS_SERVER_ALLOWED_HOSTS"] = json.dumps(["registry.example.com"])
        result = run_settings_probe(env)
        payload = json.loads(result.stdout)
        if payload.get("allowed_hosts") != ["registry.example.com"]:
            fail(f"expected configured allowed hosts, got {payload}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_test_mode_can_use_fixture_defaults() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-settings-test-mode-"))
    try:
        env = build_env(tmpdir)
        env["INFINITAS_SERVER_ENV"] = "test"
        result = run_settings_probe(env)
        payload = json.loads(result.stdout)

        if payload.get("environment") != "test":
            fail(f"expected test environment payload, got {payload}")
        if payload.get("secret_key") != "change-me":
            fail(f"expected test mode to keep fixture secret defaults, got {payload}")

        bootstrap_users = payload.get("bootstrap_users") or []
        if len(bootstrap_users) < 2:
            fail(f"expected test mode to expose fixture bootstrap users, got {payload}")
        usernames = {user.get("username") for user in bootstrap_users}
        if {"maintainer", "contributor"} - usernames:
            fail(f"expected default bootstrap usernames in test mode, got {payload}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def scenario_production_rejects_invalid_registry_read_tokens() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-settings-registry-tokens-"))
    try:
        env = build_env(tmpdir)
        env["INFINITAS_SERVER_ENV"] = "production"
        env["INFINITAS_SERVER_SECRET_KEY"] = "prod-secret-key"
        env["INFINITAS_SERVER_ALLOWED_HOSTS"] = json.dumps(["registry.example.com"])
        env["INFINITAS_SERVER_BOOTSTRAP_USERS"] = json.dumps(FIXTURE_BOOTSTRAP_USERS)

        env["INFINITAS_REGISTRY_READ_TOKENS"] = "not-json"
        malformed = run_settings_probe(env, expect=1)
        assert_contains(
            malformed.stderr + malformed.stdout,
            "INFINITAS_REGISTRY_READ_TOKENS",
            "malformed registry read tokens failure",
        )

        env["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps({"bad": True})
        non_array = run_settings_probe(env, expect=1)
        assert_contains(
            non_array.stderr + non_array.stdout,
            "INFINITAS_REGISTRY_READ_TOKENS",
            "non-array registry read tokens failure",
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> None:
    scenario_production_requires_explicit_secret()
    scenario_production_requires_explicit_bootstrap_users()
    scenario_production_requires_explicit_allowed_hosts()
    scenario_production_rejects_invalid_registry_read_tokens()
    scenario_test_mode_can_use_fixture_defaults()
    print("OK: settings hardening checks passed")


if __name__ == "__main__":
    main()
