#!/usr/bin/env python3
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def fail(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(1)


def run(command, cwd, expect=0):
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != expect:
        fail(
            f'command {command!r} exited {result.returncode}, expected {expect}\n'
            f'stdout:\n{result.stdout}\n'
            f'stderr:\n{result.stderr}'
        )
    return result


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def prepare_repo():
    tmpdir = Path(tempfile.mkdtemp(prefix='infinitas-migrations-test-'))
    repo = tmpdir / 'repo'
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns('.git', '.planning', '__pycache__', '.cache', 'scripts/__pycache__'),
    )
    return tmpdir, repo


def prepare_legacy_inputs(repo: Path):
    meta_path = repo / 'templates' / 'basic-skill' / '_meta.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta.pop('schema_version', None)
    write_json(meta_path, meta)

    target = repo / '.tmp-migration-target'
    target.mkdir(parents=True, exist_ok=True)
    manifest = {
        'repo': 'https://example.invalid/repo.git',
        'updated_at': '2026-03-12T00:00:00Z',
        'skills': {'demo-skill': {'name': 'demo-skill', 'version': '1.2.3'}},
        'history': {},
    }
    write_json(target / '.infinitas-skill-install-manifest.json', manifest)
    return meta_path, target


def assert_hosted_object_schema(repo: Path) -> None:
    db_path = repo / ".tmp-migration-schema.db"
    repo_path = repo / ".tmp-registry-repo"
    artifact_path = repo / ".tmp-registry-artifacts"
    lock_path = repo / ".tmp-registry.lock"
    repo_path.mkdir(parents=True, exist_ok=True)
    artifact_path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "INFINITAS_SERVER_DATABASE_URL": f"sqlite:///{db_path}",
            "INFINITAS_SERVER_REPO_PATH": str(repo_path),
            "INFINITAS_SERVER_ARTIFACT_PATH": str(artifact_path),
            "INFINITAS_SERVER_REPO_LOCK_PATH": str(lock_path),
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        fail(
            "expected alembic upgrade head to succeed for hosted object schema check\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    with sqlite3.connect(db_path) as conn:
        if not table_exists(conn, "registry_objects"):
            fail("expected registry_objects table to exist after migrations")

        skill_columns = table_columns(conn, "skills")
        if "registry_object_id" not in skill_columns:
            fail(
                "expected skills table to include registry_object_id after migrations, "
                f"got columns: {sorted(skill_columns)}"
            )

        draft_columns = table_columns(conn, "skill_drafts")
        for expected in ("content_mode", "content_artifact_id"):
            if expected not in draft_columns:
                fail(
                    f"expected skill_drafts table to include {expected}, "
                    f"got columns: {sorted(draft_columns)}"
                )

        version_columns = table_columns(conn, "skill_versions")
        if "sealed_manifest_json" not in version_columns:
            fail(
                "expected skill_versions table to include sealed_manifest_json after migrations, "
                f"got columns: {sorted(version_columns)}"
            )


def main():
    tmpdir, repo = prepare_repo()
    try:
        meta_path, target = prepare_legacy_inputs(repo)

        result = run([sys.executable, str(repo / 'scripts' / 'migrate-skill-meta.py'), '--check', str(meta_path)], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'would update schema_version to 1' not in combined:
            fail(f'expected skill-meta migration check output\n{combined}')

        result = run([sys.executable, str(repo / 'scripts' / 'migrate-install-manifest.py'), '--check', str(target)], cwd=repo, expect=1)
        combined = result.stdout + result.stderr
        if 'would write schema_version' not in combined:
            fail(f'expected install-manifest migration check output\n{combined}')

        run([sys.executable, str(repo / 'scripts' / 'migrate-skill-meta.py'), str(meta_path)], cwd=repo)
        run([sys.executable, str(repo / 'scripts' / 'migrate-install-manifest.py'), str(target)], cwd=repo)

        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('schema_version') != 1:
            fail(f"expected migrated skill meta to have schema_version=1, got {meta.get('schema_version')!r}")

        manifest = json.loads((target / '.infinitas-skill-install-manifest.json').read_text(encoding='utf-8'))
        if manifest.get('schema_version') != 1:
            fail(f"expected migrated install manifest to have schema_version=1, got {manifest.get('schema_version')!r}")

        assert_hosted_object_schema(repo)

        result = run([sys.executable, str(repo / 'scripts' / 'validate-registry.py')], cwd=repo)
        combined = result.stdout + result.stderr
        if 'validated ' not in combined or ' skill directories' not in combined:
            fail(f'expected migrated repo to validate\n{combined}')
    finally:
        shutil.rmtree(tmpdir)

    print('OK: migration command checks passed')


if __name__ == '__main__':
    main()
