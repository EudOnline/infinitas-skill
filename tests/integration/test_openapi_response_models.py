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


def test_authenticated_json_routes_publish_openapi_security(tmp_path: Path) -> None:
    os.environ["INFINITAS_SERVER_DATABASE_URL"] = f"sqlite:///{tmp_path / 'security.db'}"
    os.environ["INFINITAS_SERVER_SECRET_KEY"] = "response-model-test-secret-key"
    os.environ["INFINITAS_SERVER_ENV"] = "test"
    os.environ["INFINITAS_SERVER_ARTIFACT_PATH"] = str(tmp_path / "artifacts")
    os.environ["INFINITAS_SERVER_BOOTSTRAP_USERS"] = "[]"
    os.environ["INFINITAS_REGISTRY_READ_TOKENS"] = json.dumps(["reader"])

    from fastapi.routing import APIRoute

    from server.app import _dependency_requires_auth, _iter_api_routes, create_app

    app = create_app()
    schema = TestClient(app).get("/openapi.json").json()
    expected = [{"BearerAuth": []}, {"SessionCookie": []}]

    checked = []
    for route in _iter_api_routes(list(app.routes)):
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        if not _dependency_requires_auth(route.dependant):
            continue
        path_item = schema["paths"][route.path_format]
        for method in route.methods or set():
            operation = path_item.get(method.lower())
            if operation is None:
                continue
            assert operation["security"] == expected, (method, route.path, route.path_format)
            checked.append((method, route.path_format))

    assert ("GET", "/api/v1/install/me/{skill_ref}") in checked
    assert ("GET", "/api/v1/install/grant/{skill_ref}") in checked
