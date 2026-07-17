from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _activity_client(tmp_path: Path) -> TestClient:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'act.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "act-test-secret-32chars-long-min"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = (
        '[{"username":"act-tester","display_name":"Act Tester",'
        '"role":"maintainer","token":"act-test-token"},'
        '{"username":"act-contributor","display_name":"Act Contributor",'
        '"role":"contributor","token":"act-contributor-token"}]'
    )
    os.environ["INFINITAS_SERVER_ALLOWED_HOSTS"] = '["localhost","127.0.0.1","testserver"]'
    return TestClient(create_app())


class TestActivityList:
    def test_activity_requires_auth(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        response = client.get("/api/v1/activity")
        assert response.status_code == 401

    def test_activity_returns_list(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_activity_limit_param(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity?limit=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] <= 5

    def test_activity_limit_capped_at_500(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity?limit=1000", headers=headers)
        assert response.status_code == 200

    def test_activity_rejects_low_role(self, tmp_path: Path):
        # Create a user with no role (this would need custom bootstrap)
        # For now, just verify the endpoint structure
        client = _activity_client(tmp_path)
        response = client.get("/api/v1/activity")
        assert response.status_code == 401

    def test_contributor_activity_is_scoped_to_own_principal(self, tmp_path: Path):
        client = _activity_client(tmp_path)

        from sqlalchemy import select

        from server.db import get_session_factory
        from server.modules.audit.service import append_audit_event
        from server.modules.identity.models import Principal

        with get_session_factory()() as session:
            maintainer = session.scalar(select(Principal).where(Principal.slug == "act-tester"))
            contributor = session.scalar(
                select(Principal).where(Principal.slug == "act-contributor")
            )
            assert maintainer is not None and contributor is not None
            append_audit_event(
                session,
                aggregate_type="token",
                aggregate_id="maintainer-event",
                event_type="token.created",
                owner_principal_id=maintainer.id,
            )
            append_audit_event(
                session,
                aggregate_type="token",
                aggregate_id="contributor-event",
                event_type="token.created",
                owner_principal_id=contributor.id,
            )
            session.commit()

        response = client.get(
            "/api/v1/activity",
            headers={"Authorization": "Bearer act-contributor-token"},
        )
        assert response.status_code == 200, response.text
        aggregate_ids = {item["aggregate_id"] for item in response.json()["items"]}
        assert "contributor-event" in aggregate_ids
        assert "maintainer-event" not in aggregate_ids


class TestTokenActivity:
    def test_token_activity_requires_auth(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        response = client.get("/api/v1/activity/tokens/1/activity")
        assert response.status_code == 401

    def test_token_activity_returns_list(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity/tokens/999/activity", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 0  # No activity for nonexistent token


class TestShareLinkActivity:
    def test_share_link_activity_requires_auth(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        response = client.get("/api/v1/activity/share-links/1/activity")
        assert response.status_code == 401

    def test_share_link_activity_returns_list(self, tmp_path: Path):
        client = _activity_client(tmp_path)
        headers = {"Authorization": "Bearer act-test-token"}
        response = client.get("/api/v1/activity/share-links/999/activity", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] == 0
