from __future__ import annotations

import io
import json
import tarfile

from fastapi.testclient import TestClient


def build_skill_bundle(
    slug: str,
    version: str,
    *,
    extra_files: dict[str, bytes] | None = None,
    metadata_overrides: dict | None = None,
) -> bytes:
    metadata = {
        "schema_version": 1,
        "name": slug,
        "version": version,
        "status": "active",
        "summary": f"Hosted integration fixture for {slug}",
        "publisher": "fixture-publisher",
        "owner": "fixture-maintainer",
        "owners": ["fixture-maintainer"],
        "author": "fixture-maintainer",
        "maintainers": ["fixture-maintainer"],
        "agent_compatible": ["openclaw"],
        "review_state": "approved",
        "risk_level": "low",
        "distribution": {"installable": True, "channel": "hosted"},
        "tests": {"smoke": "tests/smoke.md"},
        "tags": ["hosted", "fixture"],
        "maturity": "beta",
        "quality_score": 73,
        "capabilities": ["hosted-publish", "verified-install"],
        "use_when": ["Need a hosted integration fixture"],
        "avoid_when": ["Need a production skill"],
        "runtime_assumptions": ["Hosted registry access is available"],
        "requires": {"tools": ["read"], "bins": ["git"], "env": []},
        "entrypoints": {"skill_md": "SKILL.md"},
    }
    metadata.update(metadata_overrides or {})
    entries = {
        f"{slug}/SKILL.md": (
            f"---\nname: {slug}\ndescription: Hosted fixture for {slug}.\n---\n\n"
            f"# {slug}\n\nHosted content fixture.\n"
        ).encode(),
        f"{slug}/_meta.json": (json.dumps(metadata, indent=2) + "\n").encode(),
        f"{slug}/CHANGELOG.md": f"# Changelog\n\n## {version}\n\n- Fixture.\n".encode(),
        f"{slug}/reviews.json": b'{"version":1,"requests":[],"entries":[]}\n',
        f"{slug}/tests/smoke.md": b"# Smoke test\n\nLoad the hosted fixture.\n",
        **{f"{slug}/{path}": raw for path, raw in (extra_files or {}).items()},
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for path, raw in sorted(entries.items()):
            info = tarfile.TarInfo(path)
            info.size = len(raw)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(raw))
    return buffer.getvalue()


def upload_skill_content(
    client: TestClient,
    skill_id: int,
    slug: str,
    version: str,
    headers: dict[str, str],
    *,
    bundle: bytes | None = None,
) -> dict:
    request_headers = {**headers, "Content-Type": "application/gzip"}
    response = client.post(
        f"/api/v1/skills/{skill_id}/content",
        headers=request_headers,
        content=bundle if bundle is not None else build_skill_bundle(slug, version),
    )
    assert response.status_code == 201, response.text
    return response.json()


__all__ = ["build_skill_bundle", "upload_skill_content"]
