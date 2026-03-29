#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "operate-infinitas-skill"
PUBLISHER = "lvxiaoer"
QUALIFIED_NAME = f"{PUBLISHER}/{SKILL_NAME}"
VERSION = "0.1.1"
OTHER_SKILL = "release-infinitas-skill"
OTHER_VERSION = "0.1.0"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, env=env, check=False)
    if result.returncode != expect:
        fail(
            f"command {command!r} exited {result.returncode}, expected {expect}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def make_runtime_env(db_path: Path, repo_path: Path, artifact_path: Path, lock_path: Path, port: int) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "INFINITAS_SERVER_DATABASE_URL": f"sqlite:///{db_path}",
            "INFINITAS_SERVER_REPO_PATH": str(repo_path),
            "INFINITAS_SERVER_ARTIFACT_PATH": str(artifact_path),
            "INFINITAS_SERVER_REPO_LOCK_PATH": str(lock_path),
            "INFINITAS_REGISTRY_READ_TOKENS": json.dumps(["registry-reader-token"]),
            "INFINITAS_SERVER_HOST": "127.0.0.1",
            "INFINITAS_SERVER_PORT": str(port),
        }
    )
    return env


def copy_artifact_tree(artifact_root: Path, relative_path: str) -> None:
    source = ROOT / relative_path
    target = artifact_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_release_artifacts(artifact_root: Path, *, skill_name: str, version: str) -> str:
    manifest_rel = f"catalog/distributions/{PUBLISHER}/{skill_name}/{version}/manifest.json"
    copy_artifact_tree(artifact_root, manifest_rel)
    manifest_payload = json.loads((artifact_root / manifest_rel).read_text(encoding="utf-8"))
    bundle_rel = (manifest_payload.get("bundle") or {}).get("path")
    provenance_rel = (manifest_payload.get("attestation_bundle") or {}).get("provenance_path")
    signature_rel = (manifest_payload.get("attestation_bundle") or {}).get("signature_path")
    if not bundle_rel or not provenance_rel or not signature_rel:
        fail(f"release manifest missing required artifact references: {manifest_rel}")
    for rel in [bundle_rel, provenance_rel, signature_rel]:
        copy_artifact_tree(artifact_root, rel)
    alias_rel = f"skills/{PUBLISHER}/{skill_name}/{version}/manifest.json"
    (artifact_root / alias_rel).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact_root / manifest_rel, artifact_root / alias_rel)
    return manifest_rel


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_server(base_url: str, env: dict[str, str]) -> None:
    probe = (
        "import sys, urllib.request; "
        "url=sys.argv[1]; "
        "urllib.request.urlopen(url, timeout=1).read(); "
        "print('ok')"
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        result = subprocess.run(
            ["python3", "-c", probe, base_url.removesuffix("/registry") + "/healthz"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and "ok" in result.stdout:
            return
        time.sleep(0.25)
    fail("timed out waiting for hosted registry app to start")


def main() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="infinitas-grant-install-"))
    server_process: subprocess.Popen[str] | None = None
    try:
        db_path = tmpdir / "server.db"
        repo_path = tmpdir / "repo"
        artifact_path = tmpdir / "artifacts"
        lock_path = tmpdir / "repo.lock"
        repo_path.mkdir(parents=True, exist_ok=True)
        artifact_path.mkdir(parents=True, exist_ok=True)
        port = reserve_port()
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path, port)
        os.environ.update(env)

        run(["uv", "run", "alembic", "upgrade", "head"], cwd=ROOT, env=env)

        from server import db as db_module
        from server.models import Artifact, Namespace, Release, Skill, SkillVersion
        from server.modules.access.service import create_release_exposure
        from server.settings import get_settings

        get_settings.cache_clear()
        db_module.get_engine.cache_clear()
        db_module.get_session_factory.cache_clear()
        db_module.ensure_database_ready()

        granted_manifest = copy_release_artifacts(artifact_path, skill_name=SKILL_NAME, version=VERSION)
        other_manifest = copy_release_artifacts(artifact_path, skill_name=OTHER_SKILL, version=OTHER_VERSION)

        factory = db_module.get_session_factory()
        with factory() as session:
            namespace = Namespace(slug=PUBLISHER)
            session.add(namespace)
            session.flush()

            def add_release(skill_slug: str, version: str, manifest_rel: str) -> Release:
                skill = Skill(namespace_id=namespace.id, slug=skill_slug)
                session.add(skill)
                session.flush()
                skill_version = SkillVersion(skill_id=skill.id, version=version, payload_json=json.dumps({"name": skill_slug}))
                session.add(skill_version)
                session.flush()
                release = Release(skill_version_id=skill_version.id, state="published")
                session.add(release)
                session.flush()
                session.add(Artifact(release_id=release.id, kind="manifest", digest=f"sha256:{skill_slug}", path=manifest_rel))
                return release

            granted_release = add_release(SKILL_NAME, VERSION, granted_manifest)
            other_release = add_release(OTHER_SKILL, OTHER_VERSION, other_manifest)
            session.flush()
            _, _, _, credential = create_release_exposure(
                session,
                granted_release,
                mode="grant",
                credential_token="grant-release-token",
            )
            create_release_exposure(session, other_release, mode="private")
            session.commit()
            if credential is None:
                fail("failed to seed grant credential")

        server_process = subprocess.Popen(
            [
                "uv",
                "run",
                "python3",
                "-m",
                "uvicorn",
                "server.app:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        base_url = f"http://127.0.0.1:{port}/registry"
        wait_for_server(base_url, env)

        repo = tmpdir / "client-repo"
        shutil.copytree(
            ROOT,
            repo,
            ignore=shutil.ignore_patterns(".git", ".planning", "__pycache__", ".cache", "scripts/__pycache__", ".worktrees"),
        )
        (repo / "config").mkdir(parents=True, exist_ok=True)
        (repo / "config" / "registry-sources.json").write_text(
            json.dumps(
                {
                    "$schema": "../schemas/registry-sources.schema.json",
                    "default_registry": "hosted-private",
                    "registries": [
                        {
                            "name": "hosted-private",
                            "kind": "http",
                            "base_url": base_url,
                            "enabled": True,
                            "priority": 100,
                            "trust": "private",
                            "auth": {"mode": "token", "env": "INFINITAS_REGISTRY_TOKEN"},
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        client_env = os.environ.copy()
        client_env["INFINITAS_REGISTRY_TOKEN"] = "grant-release-token"

        target_dir = tmpdir / "installed"
        result = run([str(repo / "scripts" / "install-by-name.sh"), SKILL_NAME, str(target_dir)], cwd=repo, env=client_env)
        payload = json.loads(result.stdout)
        if payload.get("state") != "installed":
            fail(f"expected hosted grant install to succeed, got {payload!r}")

        installed_skill = target_dir / SKILL_NAME
        if not installed_skill.is_dir():
            fail(f"expected installed skill directory {installed_skill}")

        blocked = subprocess.run(
            [str(repo / "scripts" / "install-by-name.sh"), OTHER_SKILL, str(tmpdir / "blocked-install")],
            cwd=repo,
            env=client_env,
            text=True,
            capture_output=True,
            check=False,
        )
        if blocked.returncode == 0:
            fail("expected non-granted skill install to fail")
        blocked_payload = json.loads(blocked.stdout)
        if blocked_payload.get("error_code") != "skill-not-found":
            fail(f"expected non-granted install to fail as skill-not-found, got {blocked_payload!r}")
    finally:
        if server_process is not None:
            server_process.terminate()
            try:
                server_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_process.kill()
                server_process.wait(timeout=10)
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("OK: private registry grant install checks passed")


if __name__ == "__main__":
    main()
