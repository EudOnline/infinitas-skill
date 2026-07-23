"""Idempotent Hosted Registry publication orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from infinitas_skill.registry.skill_source import (
    build_skill_source_bundle,
    stage_skill_source,
)


class HostedPublishError(RuntimeError):
    """Raised when a hosted publication cannot be completed safely."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PublishResult:
    payload: dict[str, Any]


_RECEIPT_FIELDS = {
    "schema_version",
    "source_path",
    "base_url",
    "qualified_name",
    "version",
    "bundle_sha256",
    "state",
    "skill_id",
    "content_id",
    "version_id",
    "release_id",
    "exposure_id",
}


def _receipt_path(
    source_dir: str | Path,
    *,
    base_url: str,
    slug: str,
    version: str,
    explicit_path: str | Path | None,
) -> Path:
    if explicit_path is not None:
        return Path(explicit_path).expanduser().resolve()
    state_root = Path(
        os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
    ).expanduser()
    identity = f"{Path(source_dir).expanduser().resolve()}\0{base_url.rstrip('/')}\0{version}"
    suffix = hashlib.sha256(identity.encode()).hexdigest()[:12]
    safe_version = re.sub(r"[^A-Za-z0-9._-]", "_", version)
    return state_root / "infinitas" / "publish" / f"{slug}-{safe_version}-{suffix}.json"


def _load_receipt(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HostedPublishError(f"could not read publish receipt {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise HostedPublishError(f"publish receipt {path} is invalid")
    return {key: payload[key] for key in _RECEIPT_FIELDS if key in payload}


def _save_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    filtered = {key: receipt[key] for key in _RECEIPT_FIELDS if key in receipt}
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(filtered, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(0o600)
        os.replace(temp_path, path)
        path.chmod(0o600)
    finally:
        temp_path.unlink(missing_ok=True)


def _update_receipt(path: Path, receipt: dict[str, Any], **changes: Any) -> None:
    receipt.update(changes)
    _save_receipt(path, receipt)


def _prepare_receipt(
    path: Path,
    *,
    source_dir: str | Path,
    base_url: str,
    qualified_name: str,
    version: str,
    bundle_sha256: str,
    require_existing: bool,
) -> dict[str, Any]:
    expected = {
        "schema_version": 1,
        "source_path": str(Path(source_dir).expanduser().resolve()),
        "base_url": base_url.rstrip("/"),
        "qualified_name": qualified_name,
        "version": version,
        "bundle_sha256": bundle_sha256,
    }
    if not path.exists():
        if require_existing:
            raise HostedPublishError(f"publish receipt does not exist: {path}")
        return {**expected, "state": "prepared"}
    receipt = _load_receipt(path)
    mismatches = [key for key, value in expected.items() if receipt.get(key) != value]
    if mismatches:
        raise HostedPublishError(
            "publish receipt does not match the current source: " + ", ".join(mismatches)
        )
    return receipt


class HostedRegistryClient:
    def __init__(self, base_url: str, token: str, *, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        if content is not None:
            headers["Content-Type"] = "application/gzip"
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                json=payload,
                content=content,
                headers=headers,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise HostedPublishError(f"registry request failed: {exc}") from exc
        try:
            body = response.json() if response.content else {}
        except ValueError as exc:
            raise HostedPublishError(
                f"registry returned invalid JSON for {method} {path}",
                status_code=response.status_code,
            ) from exc
        if response.status_code >= 400:
            detail = body.get("detail", body) if isinstance(body, dict) else body
            raise HostedPublishError(
                f"registry returned HTTP {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        return body

    def access_me(self) -> dict[str, Any]:
        body = self.request("GET", "/api/v1/access/me")
        if not isinstance(body, dict):
            raise HostedPublishError("registry access identity response is invalid")
        return body

    def list_skills(self, slug: str | None = None) -> list[dict[str, Any]]:
        query = ""
        if slug:
            query = "?" + urllib.parse.urlencode({"slug": slug})
        body = self.request("GET", f"/api/v1/skills{query}")
        if not isinstance(body, list):
            raise HostedPublishError("registry skill list response is invalid")
        return body

    def get_skill(self, skill_id: int) -> dict[str, Any]:
        body = self.request("GET", f"/api/v1/skills/{skill_id}")
        if not isinstance(body, dict):
            raise HostedPublishError("registry skill detail response is invalid")
        return body

    def create_skill(self, *, slug: str, display_name: str, summary: str) -> dict[str, Any]:
        body = self.request(
            "POST",
            "/api/v1/skills",
            payload={
                "slug": slug,
                "display_name": display_name,
                "summary": summary,
                "default_visibility_profile": "private",
            },
        )
        if not isinstance(body, dict):
            raise HostedPublishError("registry skill create response is invalid")
        return body

    def list_versions(self, skill_id: int) -> list[dict[str, Any]]:
        body = self.request("GET", f"/api/v1/skills/{skill_id}/versions")
        if not isinstance(body, list):
            raise HostedPublishError("registry version list response is invalid")
        return body

    def get_version(self, skill_id: int, version: str) -> dict[str, Any]:
        encoded = urllib.parse.quote(version, safe="")
        body = self.request("GET", f"/api/v1/skills/{skill_id}/versions/{encoded}")
        if not isinstance(body, dict):
            raise HostedPublishError("registry version detail response is invalid")
        return body

    def archive_skill(self, skill_id: int) -> dict[str, Any]:
        body = self.request("POST", f"/api/v1/skills/{skill_id}/archive", payload={})
        if not isinstance(body, dict):
            raise HostedPublishError("registry skill archive response is invalid")
        return body

    def upload_content(self, skill_id: int, bundle: bytes) -> dict[str, Any]:
        body = self.request("POST", f"/api/v1/skills/{skill_id}/content", content=bundle)
        if not isinstance(body, dict):
            raise HostedPublishError("registry content upload response is invalid")
        return body

    def create_version(self, skill_id: int, *, version: str, content_id: str) -> dict[str, Any]:
        body = self.request(
            "POST",
            f"/api/v1/skills/{skill_id}/versions",
            payload={"version": version, "content_id": content_id},
        )
        if not isinstance(body, dict):
            raise HostedPublishError("registry version create response is invalid")
        return body

    def create_release(self, version_id: int) -> dict[str, Any]:
        body = self.request("POST", f"/api/v1/versions/{version_id}/releases", payload={})
        if not isinstance(body, dict):
            raise HostedPublishError("registry release response is invalid")
        return body

    def get_release(self, release_id: int) -> dict[str, Any]:
        body = self.request("GET", f"/api/v1/releases/{release_id}")
        if not isinstance(body, dict):
            raise HostedPublishError("registry release detail response is invalid")
        return body

    def list_exposures(self, release_id: int) -> list[dict[str, Any]]:
        body = self.request("GET", f"/api/v1/releases/{release_id}/exposures")
        if not isinstance(body, list):
            raise HostedPublishError("registry exposure list response is invalid")
        return body

    def create_exposure(self, release_id: int, *, visibility: str) -> dict[str, Any]:
        body = self.request(
            "POST",
            f"/api/v1/releases/{release_id}/exposures",
            payload={
                "audience_type": visibility,
                "listing_mode": "listed",
                "install_mode": "enabled",
                "requested_review_mode": "none",
            },
        )
        if not isinstance(body, dict):
            raise HostedPublishError("registry exposure response is invalid")
        return body

    def list_releases(self, skill_id: int) -> dict[str, Any]:
        body = self.request("GET", f"/api/v1/library/{skill_id}/releases?limit=100")
        if not isinstance(body, dict):
            raise HostedPublishError("registry release list response is invalid")
        return body


def compare_versions(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_manifest = left.get("sealed_manifest") if isinstance(left, dict) else {}
    right_manifest = right.get("sealed_manifest") if isinstance(right, dict) else {}
    left_meta = left_manifest.get("metadata", {}) if isinstance(left_manifest, dict) else {}
    right_meta = right_manifest.get("metadata", {}) if isinstance(right_manifest, dict) else {}
    left_meta = left_meta if isinstance(left_meta, dict) else {}
    right_meta = right_meta if isinstance(right_meta, dict) else {}
    changed_fields = {
        key: {"from": left_meta.get(key), "to": right_meta.get(key)}
        for key in sorted(set(left_meta) | set(right_meta))
        if left_meta.get(key) != right_meta.get(key)
    }
    return {
        "left": left.get("version"),
        "right": right.get("version"),
        "content_changed": left.get("content_digest") != right.get("content_digest"),
        "metadata_changed": left.get("metadata_digest") != right.get("metadata_digest"),
        "changed_metadata_fields": changed_fields,
    }


def _wait_for_release(
    client: HostedRegistryClient,
    release_id: int,
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        release = client.get_release(release_id)
        state = str(release.get("state") or "")
        if state in {"ready", "failed", "withdrawn"}:
            if state != "ready":
                raise HostedPublishError(f"release {release_id} ended in state {state}")
            return release
        if time.monotonic() >= deadline:
            raise HostedPublishError(f"timed out waiting for release {release_id}")
        time.sleep(1)


def _resolve_or_create_skill(
    client: HostedRegistryClient,
    *,
    slug: str,
    display_name: str,
    summary: str,
) -> dict[str, Any]:
    matches = client.list_skills(slug)
    if len(matches) > 1:
        raise HostedPublishError(f"registry returned multiple skills for slug {slug!r}")
    if matches:
        return matches[0]
    try:
        return client.create_skill(slug=slug, display_name=display_name, summary=summary)
    except HostedPublishError as exc:
        if exc.status_code != 409:
            raise
        matches = client.list_skills(slug)
        if len(matches) != 1:
            raise HostedPublishError(
                "skill creation conflicted but exact skill could not be resolved"
            )
        return matches[0]


def _resolve_version(
    client: HostedRegistryClient,
    *,
    skill_id: int,
    version: str,
    bundle_digest: str,
    bundle: bytes,
    receipt: dict[str, Any],
    receipt_path: Path,
) -> dict[str, Any]:
    expected_digest = f"sha256:{bundle_digest}"
    versions = client.list_versions(skill_id)
    existing = next((item for item in versions if item.get("version") == version), None)
    if existing is not None:
        if existing.get("content_digest") != expected_digest:
            raise HostedPublishError(
                f"version {version} already exists with a different content digest"
            )
        _update_receipt(
            receipt_path,
            receipt,
            state="version-created",
            version_id=int(existing["id"]),
        )
        return {"version": existing, "reused": True}
    content_id = str(receipt.get("content_id") or "")
    content: dict[str, Any] | None = None
    if not content_id:
        content = client.upload_content(skill_id, bundle)
        content_id = str(content.get("content_id") or "")
        if content_id:
            _update_receipt(
                receipt_path,
                receipt,
                state="content-uploaded",
                content_id=content_id,
            )
    if not content_id:
        raise HostedPublishError("registry upload did not return content_id")
    created = client.create_version(skill_id, version=version, content_id=content_id)
    _update_receipt(
        receipt_path,
        receipt,
        state="version-created",
        version_id=int(created["id"]),
    )
    return {"version": created, "content": content, "reused": False}


def _publish_prepared(
    client: HostedRegistryClient,
    *,
    staged: Any,
    version: str,
    visibility: str,
    wait: bool,
    timeout_seconds: int,
    bundle: bytes,
    digest: str,
    prepared: dict[str, Any],
    receipt: dict[str, Any],
    receipt_path: Path,
) -> PublishResult:
    skill = _resolve_or_create_skill(
        client,
        slug=staged.slug,
        display_name=staged.metadata["summary"],
        summary=staged.metadata["summary"],
    )
    skill_id = int(skill["id"])
    _update_receipt(receipt_path, receipt, state="skill-resolved", skill_id=skill_id)
    version_result = _resolve_version(
        client,
        skill_id=skill_id,
        version=version,
        bundle_digest=digest,
        bundle=bundle,
        receipt=receipt,
        receipt_path=receipt_path,
    )
    version_view = version_result["version"]
    release = client.create_release(int(version_view["id"]))
    release_id = int(release["id"])
    _update_receipt(receipt_path, receipt, state="release-created", release_id=release_id)
    if wait:
        release = _wait_for_release(client, release_id, timeout_seconds=timeout_seconds)
    elif str(release.get("state") or "") != "ready":
        return PublishResult(
            {
                "state": "release-created",
                "prepared": prepared,
                "skill": skill,
                "version": version_view,
                "release": release,
                "exposure": None,
                "reused_version": bool(version_result["reused"]),
                "receipt_path": str(receipt_path),
            }
        )
    exposures = client.list_exposures(release_id)
    exposure = next(
        (
            item
            for item in exposures
            if item.get("audience_type") == visibility
            and item.get("state") not in {"revoked", "rejected"}
        ),
        None,
    )
    if exposure is None:
        exposure = client.create_exposure(release_id, visibility=visibility)
    _update_receipt(receipt_path, receipt, state="published", exposure_id=int(exposure["id"]))
    return PublishResult(
        {
            "state": "published",
            "prepared": prepared,
            "skill": skill,
            "version": version_view,
            "release": release,
            "exposure": exposure,
            "reused_version": bool(version_result["reused"]),
            "receipt_path": str(receipt_path),
        }
    )


def publish_skill(
    source_dir: str | Path,
    *,
    base_url: str,
    token: str,
    version: str,
    repo_root: str | Path,
    visibility: str = "private",
    wait: bool = True,
    timeout_seconds: int = 120,
    dry_run: bool = False,
    receipt_path: str | Path | None = None,
    resume: bool = False,
) -> PublishResult:
    """Normalize, publish, and expose one local skill idempotently."""
    client = HostedRegistryClient(base_url, token)
    identity = client.access_me()
    publisher = str(identity.get("principal_slug") or "")
    if not publisher:
        raise HostedPublishError("publisher identity is missing from access/me")
    with tempfile.TemporaryDirectory(prefix="infinitas-publish-") as temp_dir:
        staged = stage_skill_source(
            source_dir,
            Path(temp_dir),
            publisher=publisher,
            version=version,
        )
        bundle_path = build_skill_source_bundle(
            staged,
            Path(temp_dir) / f"{staged.slug}-{version}.tar.gz",
            repo_root=repo_root,
        )
        bundle = bundle_path.read_bytes()
        digest = hashlib.sha256(bundle).hexdigest()
        prepared = {
            "qualified_name": staged.qualified_name,
            "slug": staged.slug,
            "version": version,
            "bundle_sha256": f"sha256:{digest}",
            "bundle_size_bytes": len(bundle),
            "generated_files": list(staged.generated_files),
        }
        if dry_run:
            return PublishResult({"state": "dry-run", "prepared": prepared})

        resolved_receipt_path = _receipt_path(
            source_dir,
            base_url=base_url,
            slug=staged.slug,
            version=version,
            explicit_path=receipt_path,
        )
        receipt = _prepare_receipt(
            resolved_receipt_path,
            source_dir=source_dir,
            base_url=base_url,
            qualified_name=staged.qualified_name,
            version=version,
            bundle_sha256=str(prepared["bundle_sha256"]),
            require_existing=resume,
        )
        _save_receipt(resolved_receipt_path, receipt)

        return _publish_prepared(
            client,
            staged=staged,
            version=version,
            visibility=visibility,
            wait=wait,
            timeout_seconds=timeout_seconds,
            bundle=bundle,
            digest=digest,
            prepared=prepared,
            receipt=receipt,
            receipt_path=resolved_receipt_path,
        )


__all__ = [
    "HostedPublishError",
    "HostedRegistryClient",
    "PublishResult",
    "_publish_prepared",
    "compare_versions",
    "publish_skill",
]
