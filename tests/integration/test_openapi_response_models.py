from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient


def test_agent_json_routes_publish_named_response_models(tmp_path: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'responses.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "response-model-test-secret-key"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = "[]"
    os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["reader"])

    from server.app import create_app

    schema = TestClient(create_app()).get("/openapi.json").json()
    routes = {
        ("/api/v1/search", "get"),
        ("/api/v1/auth/logout", "post"),
        ("/api/v1/auth/csrf", "get"),
        ("/api/v1/auth/me", "get"),
        ("/api/v1/profile/me", "get"),
        ("/api/v1/profile/{credential_id}", "get"),
        ("/api/v1/credentials/{credential_id}/policy", "patch"),
        ("/api/v1/registry/ai-index.json", "get"),
        ("/api/v1/registry/discovery-index.json", "get"),
        ("/api/v1/registry/distributions.json", "get"),
        ("/api/v1/registry/compatibility.json", "get"),
    }

    for path, method in routes:
        response_schema = schema["paths"][path][method]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert "$ref" in response_schema, (path, method, response_schema)
