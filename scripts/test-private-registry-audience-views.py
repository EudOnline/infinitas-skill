#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(cmd: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def make_runtime_env(db_path: Path, repo_path: Path, artifact_path: Path, lock_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "INFINITAS_SERVER_DATABASE_URL": f"sqlite:///{db_path}",
            "INFINITAS_SERVER_REPO_PATH": str(repo_path),
            "INFINITAS_SERVER_ARTIFACT_PATH": str(artifact_path),
            "INFINITAS_SERVER_REPO_LOCK_PATH": str(lock_path),
            "INFINITAS_REGISTRY_READ_TOKENS": json.dumps(["registry-reader-token"]),
        }
    )
    return env


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_distribution_artifacts(
    artifact_root: Path,
    *,
    publisher: str,
    name: str,
    version: str,
    summary: str,
) -> str:
    manifest_rel = f"catalog/distributions/{publisher}/{name}/{version}/manifest.json"
    bundle_rel = f"catalog/distributions/{publisher}/{name}/{version}/skill.tar.gz"
    provenance_rel = f"catalog/provenance/{name}-{version}.json"
    signature_rel = f"catalog/provenance/{name}-{version}.json.ssig"

    write_json(
        artifact_root / manifest_rel,
        {
            "$schema": "schemas/distribution-manifest.schema.json",
            "schema_version": 1,
            "kind": "skill-distribution-manifest",
            "generated_at": "2026-03-29T00:00:00Z",
            "skill": {
                "name": name,
                "publisher": publisher,
                "qualified_name": f"{publisher}/{name}",
                "identity_mode": "qualified",
                "version": version,
                "status": "active",
                "summary": summary,
                "depends_on": [],
                "conflicts_with": [],
            },
            "source_snapshot": {
                "kind": "git-tag",
                "tag": f"skill/{name}/v{version}",
                "ref": f"refs/tags/skill/{name}/v{version}",
                "commit": "0" * 40,
            },
            "bundle": {
                "path": bundle_rel,
                "format": "tar.gz",
                "sha256": "a" * 64,
                "size": 12,
                "root_dir": name,
                "file_count": 1,
            },
            "attestation_bundle": {
                "provenance_path": provenance_rel,
                "signature_path": signature_rel,
                "provenance_sha256": "b" * 64,
                "signature_sha256": "c" * 64,
                "signer_identity": publisher,
                "namespace": "tests",
                "allowed_signers": "config/allowed_signers",
                "required_formats": ["ssh"],
            },
            "dependencies": {
                "mode": "install",
                "root": {
                    "name": name,
                    "publisher": publisher,
                    "qualified_name": f"{publisher}/{name}",
                    "version": version,
                    "registry": "self",
                    "stage": "active",
                    "path": manifest_rel,
                    "source_type": "distribution-manifest",
                    "distribution_manifest": manifest_rel,
                    "source_snapshot_tag": f"skill/{name}/v{version}",
                    "source_snapshot_commit": "0" * 40,
                },
                "steps": [],
                "registries_consulted": ["self"],
            },
            "file_manifest": [
                {
                    "path": "SKILL.md",
                    "sha256": "d" * 64,
                    "size": 7,
                    "mode": "0644",
                }
            ],
            "build": {
                "archive_format": "tar.gz",
            },
        },
    )
    (artifact_root / bundle_rel).write_bytes(b"bundle-data\n")
    write_json(
        artifact_root / provenance_rel,
        {
            "attestation": {
                "format": "ssh",
                "signature_ext": ".ssig",
            }
        },
    )
    (artifact_root / signature_rel).write_text("signature\n", encoding="utf-8")

    # Keep the legacy hosted alias paths present so the file-serving routes can resolve them.
    alias_rel = f"skills/{publisher}/{name}/{version}/manifest.json"
    write_json(artifact_root / alias_rel, {"name": name, "version": version})
    return manifest_rel


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="infinitas-audience-views-") as tmp:
        tmpdir = Path(tmp)
        db_path = tmpdir / "server.db"
        repo_path = tmpdir / "repo"
        artifact_path = tmpdir / "artifacts"
        lock_path = tmpdir / "repo.lock"
        repo_path.mkdir(parents=True, exist_ok=True)
        artifact_path.mkdir(parents=True, exist_ok=True)
        env = make_runtime_env(db_path, repo_path, artifact_path, lock_path)
        os.environ.update(env)

        upgrade = run(["uv", "run", "alembic", "upgrade", "head"], env=env)
        if upgrade.returncode != 0:
            fail(
                "alembic upgrade head failed.\n"
                f"stdout:\n{upgrade.stdout}\n"
                f"stderr:\n{upgrade.stderr}"
            )

        from fastapi.testclient import TestClient
        from server import db as db_module
        from server.app import create_app
        from server.models import Artifact, Namespace, Release, Skill, SkillVersion
        from server.modules.access.service import create_release_exposure
        from server.settings import get_settings

        get_settings.cache_clear()
        db_module.get_engine.cache_clear()
        db_module.get_session_factory.cache_clear()
        db_module.ensure_database_ready()

        private_manifest = write_distribution_artifacts(
            artifact_path,
            publisher="acme",
            name="alpha-private",
            version="1.0.0",
            summary="private summary",
        )
        grant_manifest = write_distribution_artifacts(
            artifact_path,
            publisher="acme",
            name="beta-grant",
            version="1.0.0",
            summary="grant summary",
        )
        approved_manifest = write_distribution_artifacts(
            artifact_path,
            publisher="acme",
            name="gamma-public-approved",
            version="1.0.0",
            summary="approved summary",
        )
        pending_manifest = write_distribution_artifacts(
            artifact_path,
            publisher="acme",
            name="delta-public-pending",
            version="1.0.0",
            summary="pending summary",
        )

        factory = db_module.get_session_factory()
        with factory() as session:
            namespace = Namespace(slug="acme")
            session.add(namespace)
            session.flush()

            def add_release(skill_slug: str, version: str, manifest_rel: str) -> Release:
                skill = Skill(namespace_id=namespace.id, slug=skill_slug)
                session.add(skill)
                session.flush()
                skill_version = SkillVersion(
                    skill_id=skill.id,
                    version=version,
                    payload_json=json.dumps({"summary": skill_slug}),
                )
                session.add(skill_version)
                session.flush()
                release = Release(skill_version_id=skill_version.id, state="published")
                session.add(release)
                session.flush()
                session.add(Artifact(release_id=release.id, kind="manifest", digest=f"sha256:{skill_slug}", path=manifest_rel))
                return release

            private_release = add_release("alpha-private", "1.0.0", private_manifest)
            grant_release = add_release("beta-grant", "1.0.0", grant_manifest)
            approved_release = add_release("gamma-public-approved", "1.0.0", approved_manifest)
            pending_release = add_release("delta-public-pending", "1.0.0", pending_manifest)
            session.flush()

            create_release_exposure(session, private_release, mode="private")
            _, _, _, credential = create_release_exposure(
                session,
                grant_release,
                mode="grant",
                credential_token="grant-release-token",
            )
            _, approved_case, _, _ = create_release_exposure(session, approved_release, mode="public")
            _, pending_case, _, _ = create_release_exposure(session, pending_release, mode="public")
            approved_case.status = "approved"
            session.flush()
            session.commit()

            if credential is None or pending_case is None:
                fail("failed to seed access policy fixtures")

        app = create_app()
        with TestClient(app) as client:
            home = client.get("/")
            if home.status_code != 200:
                fail(f"expected home page 200, got {home.status_code}: {home.text}")
            for visible_name in ["gamma-public-approved"]:
                if visible_name not in home.text:
                    fail(f"expected anonymous home to include {visible_name!r}")
            for hidden_name in ["alpha-private", "beta-grant", "delta-public-pending"]:
                if hidden_name in home.text:
                    fail(f"expected anonymous home to hide {hidden_name!r}")

            search = client.get(
                "/api/search?q=alpha&lang=en",
                headers={"Authorization": "Bearer dev-maintainer-token"},
            )
            if search.status_code != 200:
                fail(f"expected internal search to return 200, got {search.status_code}: {search.text}")
            search_payload = search.json()
            search_names = [item.get("qualified_name") for item in search_payload.get("skills", [])]
            if "acme/alpha-private" not in search_names:
                fail(f"expected internal search to include private release, got {search_names!r}")

            reader_ai = client.get(
                "/registry/ai-index.json",
                headers={"Authorization": "Bearer registry-reader-token"},
            )
            if reader_ai.status_code != 200:
                fail(f"expected registry reader ai-index to return 200, got {reader_ai.status_code}: {reader_ai.text}")
            reader_skill_names = sorted(
                item.get("qualified_name") for item in (reader_ai.json().get("skills") or []) if isinstance(item, dict)
            )
            expected_reader = sorted(
                [
                    "acme/alpha-private",
                    "acme/beta-grant",
                    "acme/delta-public-pending",
                    "acme/gamma-public-approved",
                ]
            )
            if reader_skill_names != expected_reader:
                fail(f"expected registry reader to see all exposed releases, got {reader_skill_names!r}")

            grant_ai = client.get(
                "/registry/ai-index.json",
                headers={"Authorization": "Bearer grant-release-token"},
            )
            if grant_ai.status_code != 200:
                fail(f"expected grant ai-index to return 200, got {grant_ai.status_code}: {grant_ai.text}")
            grant_skill_names = [
                item.get("qualified_name") for item in (grant_ai.json().get("skills") or []) if isinstance(item, dict)
            ]
            if grant_skill_names != ["acme/beta-grant"]:
                fail(f"expected grant ai-index to contain only the granted release, got {grant_skill_names!r}")

            grant_discovery = client.get(
                "/registry/discovery-index.json",
                headers={"Authorization": "Bearer grant-release-token"},
            )
            if grant_discovery.status_code != 200:
                fail(
                    f"expected grant discovery-index to return 200, got {grant_discovery.status_code}: {grant_discovery.text}"
                )
            discovery_names = [
                item.get("qualified_name")
                for item in (grant_discovery.json().get("skills") or [])
                if isinstance(item, dict)
            ]
            if discovery_names != ["acme/beta-grant"]:
                fail(f"expected grant discovery view to contain only the granted release, got {discovery_names!r}")

            allowed_manifest = client.get(
                "/registry/catalog/distributions/acme/beta-grant/1.0.0/manifest.json",
                headers={"Authorization": "Bearer grant-release-token"},
            )
            if allowed_manifest.status_code != 200:
                fail(
                    "expected grant credential to read granted distribution manifest, "
                    f"got {allowed_manifest.status_code}: {allowed_manifest.text}"
                )

            denied_manifest = client.get(
                "/registry/catalog/distributions/acme/alpha-private/1.0.0/manifest.json",
                headers={"Authorization": "Bearer grant-release-token"},
            )
            if denied_manifest.status_code != 403:
                fail(f"expected non-granted manifest to return 403, got {denied_manifest.status_code}: {denied_manifest.text}")

            allowed_provenance = client.get(
                "/registry/catalog/provenance/beta-grant-1.0.0.json",
                headers={"Authorization": "Bearer grant-release-token"},
            )
            if allowed_provenance.status_code != 200:
                fail(
                    "expected grant credential to read granted provenance, "
                    f"got {allowed_provenance.status_code}: {allowed_provenance.text}"
                )

    print("OK: private registry audience view checks passed")


if __name__ == "__main__":
    main()
