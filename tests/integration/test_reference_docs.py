from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_web_admin_and_agent_docs_freeze_the_new_product_contract() -> None:
    spec = _read_text("docs/specs/web-admin-agent-product-contract.md")
    quickstart = _read_text("docs/guide/quickstart.md")
    registry_cli = _read_text("docs/reference/registry-cli.md")
    error_catalog = _read_text("docs/reference/error-catalog.md")
    deployment = _read_text("docs/ops/server-deployment.md")
    frontend_alignment = _read_text("docs/guide/frontend-control-plane-alignment.md")
    combined = "\n".join(
        (spec, quickstart, registry_cli, error_catalog, deployment, frontend_alignment)
    )

    for required in (
        "/library",
        "/access",
        "/shares",
        "/activity",
        "GET /api/library",
        "PUT /api/publish/objects/{slug}",
        "POST /api/publish/objects/{object_id}/releases",
        "GET /api/publish/releases/{release_id}/status",
        "Object",
        "Release",
        "Visibility",
        "Token",
        "Share Link",
        "Activity",
        "kimi cli",
    ):
        assert required in combined

    assert "Maintainer-only console" not in combined
    assert "maintainer-console" not in combined
    assert "Compatibility authoring flow" not in combined
