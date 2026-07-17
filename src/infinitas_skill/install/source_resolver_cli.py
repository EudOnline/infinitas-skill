import argparse
import json
from pathlib import Path
from typing import Any

from infinitas_skill.install.distribution_index import load_distribution_index
from infinitas_skill.install.http_registry import (
    HostedRegistryError,
    fetch_json,
    registry_catalog_path,
)
from infinitas_skill.install.registry_source_primitives import (
    normalized_auth,
    resolve_registry_root,
)
from infinitas_skill.install.registry_sources import (
    apply_registry_federation,
    find_registry,
    load_registry_config,
    registry_identity,
    registry_is_resolution_candidate,
    registry_uses_refresh_cache,
)
from infinitas_skill.install.source_candidate_selection import (
    matching_candidates,
    select_candidate,
)
from infinitas_skill.policy.skill_identity import normalize_skill_identity, parse_requested_skill
from infinitas_skill.registry.refresh_state import (
    evaluate_refresh_status,
    refresh_resolution_message,
    refresh_status_blocks_resolution,
)
from infinitas_skill.registry.snapshot import resolve_snapshot_selector
from infinitas_skill.root import ROOT

JsonDict = dict[str, Any]


class SourceResolutionError(Exception):
    """Raised when no installable source matches a resolution request."""


def expected_skill_tag(name: object, version: object) -> str | None:
    if not name or not version:
        return None
    return f"skill/{name}/v{version}"


def append_registry_item(reg: JsonDict, items: list[JsonDict], payload: object) -> None:
    resolved = apply_registry_federation(reg, payload)
    if resolved is not None:
        items.append(resolved)


def decorate_registry_freshness(payload: JsonDict, status: JsonDict) -> JsonDict:
    decorated = dict(payload)
    warning = refresh_resolution_message(status)
    decorated.update(
        {
            "registry_has_refresh_state": status.get("has_state"),
            "registry_refresh_state_file": status.get("state_file"),
            "registry_refresh_age_seconds": status.get("age_seconds"),
            "registry_refresh_age_hours": status.get("age_hours"),
            "registry_freshness_state": status.get("freshness_state"),
            "registry_freshness_warning": warning,
        }
    )
    return decorated


def _resolved_output_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value.strip())
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    return path


def _skill_registry_item(
    *,
    reg_root: Path,
    reg_info: JsonDict,
    snapshot_fields: JsonDict,
    stage: str,
    skill_dir: Path,
    meta: JsonDict,
    identity: JsonDict,
    distribution: JsonDict | None,
    default_source_type: str,
) -> JsonDict:
    dist = distribution or {}
    manifest_path = dist.get("manifest_path")
    if distribution:
        if not isinstance(manifest_path, str):
            raise SourceResolutionError("distribution is missing manifest_path")
        resolved_path = str((reg_root / manifest_path).resolve())
    else:
        resolved_path = str(skill_dir)
    return {
        **reg_info,
        **snapshot_fields,
        "stage": dist.get("status") if distribution else stage,
        "path": resolved_path,
        "skill_path": str(skill_dir),
        "relative_path": dist.get("manifest_path")
        if distribution
        else str(skill_dir.relative_to(reg_root)),
        "dir_name": skill_dir.name,
        "name": meta.get("name"),
        "publisher": identity.get("publisher"),
        "qualified_name": identity.get("qualified_name"),
        "identity_mode": identity.get("identity_mode"),
        "version": meta.get("version"),
        "status": meta.get("status"),
        "snapshot_of": meta.get("snapshot_of"),
        "snapshot_created_at": meta.get("snapshot_created_at"),
        "snapshot_label": meta.get("snapshot_label"),
        "installable": bool(meta.get("distribution", {}).get("installable", True)),
        "expected_tag": dist.get("source_snapshot_tag")
        if distribution
        else expected_skill_tag(meta.get("name"), meta.get("version")),
        "source_type": "distribution-manifest" if distribution else default_source_type,
        "distribution_manifest": dist.get("manifest_path") if distribution else None,
        "distribution_bundle": dist.get("bundle_path") if distribution else None,
        "distribution_bundle_sha256": dist.get("bundle_sha256") if distribution else None,
        "distribution_attestation": dist.get("attestation_path") if distribution else None,
        "distribution_attestation_signature": dist.get("attestation_signature_path")
        if distribution
        else None,
        "source_snapshot_kind": dist.get("source_snapshot_kind") if distribution else None,
        "source_snapshot_tag": dist.get("source_snapshot_tag") if distribution else None,
        "source_snapshot_ref": dist.get("source_snapshot_ref") if distribution else None,
        "source_snapshot_commit": dist.get("source_snapshot_commit") if distribution else None,
        "registry_commit": dist.get("source_snapshot_commit")
        if distribution
        else reg_info.get("registry_commit"),
        "registry_tag": dist.get("source_snapshot_tag")
        if distribution
        else reg_info.get("registry_tag"),
        "registry_ref": dist.get("source_snapshot_ref")
        if distribution
        else reg_info.get("registry_ref"),
    }


def _distribution_registry_item(
    reg_root: Path,
    reg_info: JsonDict,
    snapshot_fields: JsonDict,
    distribution: JsonDict,
) -> JsonDict:
    manifest_path = distribution.get("manifest_path")
    if not isinstance(manifest_path, str):
        raise SourceResolutionError("distribution is missing manifest_path")
    return {
        **reg_info,
        **snapshot_fields,
        "stage": distribution.get("status") or "archived",
        "path": str((reg_root / manifest_path).resolve()),
        "skill_path": None,
        "relative_path": distribution.get("manifest_path"),
        "dir_name": Path(distribution.get("manifest_path") or "").parent.name,
        "name": distribution.get("name"),
        "publisher": distribution.get("publisher"),
        "qualified_name": distribution.get("qualified_name"),
        "identity_mode": distribution.get("identity_mode"),
        "version": distribution.get("version"),
        "status": distribution.get("status"),
        "snapshot_of": None,
        "snapshot_created_at": distribution.get("generated_at"),
        "snapshot_label": None,
        "installable": True,
        "expected_tag": distribution.get("source_snapshot_tag")
        or expected_skill_tag(distribution.get("name"), distribution.get("version")),
        "source_type": "distribution-manifest",
        "distribution_manifest": distribution.get("manifest_path"),
        "distribution_bundle": distribution.get("bundle_path"),
        "distribution_bundle_sha256": distribution.get("bundle_sha256"),
        "distribution_attestation": distribution.get("attestation_path"),
        "distribution_attestation_signature": distribution.get("attestation_signature_path"),
        "source_snapshot_kind": distribution.get("source_snapshot_kind"),
        "source_snapshot_tag": distribution.get("source_snapshot_tag"),
        "source_snapshot_ref": distribution.get("source_snapshot_ref"),
        "source_snapshot_commit": distribution.get("source_snapshot_commit"),
        "registry_commit": distribution.get("source_snapshot_commit")
        or reg_info.get("registry_commit"),
        "registry_tag": distribution.get("source_snapshot_tag") or reg_info.get("registry_tag"),
        "registry_ref": distribution.get("source_snapshot_ref") or reg_info.get("registry_ref"),
    }


def scan_registry(
    reg: JsonDict,
    *,
    reg_root: str | Path | None = None,
    reg_info: JsonDict | None = None,
    default_source_type: str = "working-tree",
    snapshot_fields: JsonDict | None = None,
) -> list[JsonDict]:
    if reg.get("kind") == "http":
        return scan_http_registry(reg)
    reg_root = (
        Path(reg_root).resolve() if reg_root is not None else resolve_registry_root(ROOT, reg)
    )
    if reg_root is None or not reg_root.exists():
        return []
    reg_info = dict(reg_info or registry_identity(ROOT, reg))
    snapshot_fields = dict(snapshot_fields or {})
    distribution_index = load_distribution_index(reg_root)
    distribution_by_identity = {
        (entry.get("qualified_name") or entry.get("name"), entry.get("version")): entry
        for entry in distribution_index
    }
    matched_distribution: set[tuple[object, object]] = set()
    items: list[dict[str, Any]] = []
    skills_root = reg_root / "skills"
    for stage in ["active", "incubating", "archived"]:
        stage_dir = skills_root / stage
        if not stage_dir.exists():
            continue
        for d in sorted(
            p for p in stage_dir.iterdir() if p.is_dir() and (p / "_meta.json").exists()
        ):
            try:
                meta = json.loads((d / "_meta.json").read_text(encoding="utf-8"))
            except Exception:
                continue
            identity = normalize_skill_identity(meta)
            distribution = distribution_by_identity.get(
                (identity.get("qualified_name") or meta.get("name"), meta.get("version"))
            )
            append_registry_item(
                reg,
                items,
                _skill_registry_item(
                    reg_root=reg_root,
                    reg_info=reg_info,
                    snapshot_fields=snapshot_fields,
                    stage=stage,
                    skill_dir=d,
                    meta=meta,
                    identity=identity,
                    distribution=distribution,
                    default_source_type=default_source_type,
                ),
            )
            if distribution:
                matched_distribution.add(
                    (identity.get("qualified_name") or meta.get("name"), meta.get("version"))
                )

    for distribution in distribution_index:
        key = (
            distribution.get("qualified_name") or distribution.get("name"),
            distribution.get("version"),
        )
        if key in matched_distribution:
            continue
        append_registry_item(
            reg,
            items,
            _distribution_registry_item(reg_root, reg_info, snapshot_fields, distribution),
        )
    return items


def scan_http_registry(reg: JsonDict) -> list[JsonDict]:
    reg_info = registry_identity(ROOT, reg)
    auth = normalized_auth(reg)
    base_url = reg.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        return []
    try:
        payload = fetch_json(
            base_url,
            registry_catalog_path(reg, "ai_index"),
            token_env=auth.get("env") if auth.get("mode") == "token" else None,
        )
    except HostedRegistryError:
        return []

    items: list[dict[str, Any]] = []
    for skill in payload.get("skills") or []:
        if not isinstance(skill, dict):
            continue
        name = skill.get("name")
        qualified_name = skill.get("qualified_name") or name
        publisher = skill.get("publisher")
        versions = skill.get("versions") or {}
        default_version = skill.get("default_install_version") or skill.get("latest_version")
        for version, version_info in versions.items():
            if not isinstance(version_info, dict):
                continue
            stage = "active" if version == default_version else "archived"
            append_registry_item(
                reg,
                items,
                {
                    **reg_info,
                    "stage": stage,
                    "path": version_info.get("manifest_path"),
                    "skill_path": None,
                    "relative_path": version_info.get("manifest_path"),
                    "dir_name": name,
                    "name": name,
                    "publisher": publisher,
                    "qualified_name": qualified_name,
                    "identity_mode": skill.get("identity_mode"),
                    "version": version,
                    "status": stage,
                    "snapshot_of": None,
                    "snapshot_created_at": version_info.get("published_at"),
                    "snapshot_label": None,
                    "installable": bool(version_info.get("installable", True)),
                    "expected_tag": expected_skill_tag(name, version),
                    "source_type": "distribution-manifest",
                    "distribution_manifest": version_info.get("manifest_path"),
                    "distribution_bundle": version_info.get("bundle_path"),
                    "distribution_bundle_sha256": version_info.get("bundle_sha256"),
                    "distribution_attestation": version_info.get("attestation_path"),
                    "distribution_attestation_signature": version_info.get(
                        "attestation_signature_path"
                    ),
                    "source_snapshot_kind": None,
                    "source_snapshot_tag": None,
                    "source_snapshot_ref": None,
                    "source_snapshot_commit": None,
                    "registry_commit": None,
                    "registry_tag": None,
                    "registry_ref": None,
                },
            )
    return items


def load_candidates(
    registry: str | None = None, snapshot: str | None = None
) -> tuple[JsonDict, list[JsonDict], list[JsonDict]]:
    cfg = load_registry_config(ROOT)
    items: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    explicit_registry = bool(registry)

    if snapshot:
        if not registry:
            raise SystemExit("--snapshot requires --registry")
        reg = find_registry(cfg, registry)
        if reg is None:
            raise SystemExit(f"unknown registry: {registry}")
        snapshot_record = resolve_snapshot_selector(ROOT, registry, snapshot)
        if snapshot_record is None:
            raise SystemExit(f"snapshot '{snapshot}' not found for registry '{registry}'")

        summary = snapshot_record.get("summary") or {}
        metadata = snapshot_record.get("metadata") or {}
        raw_source_registry = metadata.get("source_registry")
        source_registry = raw_source_registry if isinstance(raw_source_registry, dict) else {}
        snapshot_root = _resolved_output_path(summary.get("snapshot_root")) or snapshot_record.get(
            "snapshot_root"
        )
        if snapshot_root is None or not Path(snapshot_root).exists():
            snapshot_id = summary.get("snapshot_id") or snapshot
            raise SystemExit(
                f"snapshot {snapshot_id!r} for registry {registry!r} is missing its registry tree"
            )

        reg_info = registry_identity(ROOT, reg)
        reg_info.update(
            {
                "registry_root": summary.get("snapshot_root") or reg_info.get("registry_root"),
                "registry_commit": summary.get("source_commit") or reg_info.get("registry_commit"),
                "registry_ref": summary.get("source_ref") or reg_info.get("registry_ref"),
                "registry_tag": summary.get("source_tag") or reg_info.get("registry_tag"),
                "registry_trust": source_registry.get("trust") or reg_info.get("registry_trust"),
                "registry_update_mode": source_registry.get("update_mode")
                or reg_info.get("registry_update_mode"),
                "registry_origin_url": source_registry.get("origin_url")
                or reg_info.get("registry_origin_url"),
            }
        )
        snapshot_fields = {
            "registry_snapshot_id": summary.get("snapshot_id"),
            "registry_snapshot_path": summary.get("snapshot_root"),
            "registry_snapshot_created_at": summary.get("created_at"),
            "registry_snapshot_metadata_path": summary.get("metadata_path"),
            "registry_snapshot_authoritative": summary.get("authoritative"),
        }
        reg_items = scan_registry(
            reg,
            reg_root=snapshot_root,
            reg_info=reg_info,
            default_source_type="registry-snapshot",
            snapshot_fields=snapshot_fields,
        )
        return cfg, reg_items, blocked

    for reg in cfg.get("registries", []):
        if not reg.get("enabled", True):
            continue
        if registry and reg.get("name") != registry:
            continue
        if not registry_is_resolution_candidate(reg, explicit_registry=explicit_registry):
            continue
        freshness = evaluate_refresh_status(ROOT, reg) if registry_uses_refresh_cache(reg) else None
        if freshness and refresh_status_blocks_resolution(freshness):
            blocked.append(
                {
                    "registry": reg.get("name"),
                    "message": refresh_resolution_message(freshness),
                    "freshness": freshness,
                }
            )
            continue
        reg_items = scan_registry(reg)
        if freshness:
            reg_items = [decorate_registry_freshness(item, freshness) for item in reg_items]
        items.extend(reg_items)
    return cfg, items, blocked


def _resolution_failure_message(
    *,
    cfg: dict[str, Any],
    blocked: list[dict[str, Any]],
    registry: str | None,
    name: str,
    version: str | None,
) -> str:
    if registry:
        blocked_registry = next(
            (item for item in blocked if item.get("registry") == registry), None
        )
        if blocked_registry and blocked_registry.get("message"):
            return str(blocked_registry["message"])
        reg = find_registry(cfg, registry)
        if reg and registry_uses_refresh_cache(reg):
            freshness = evaluate_refresh_status(ROOT, reg)
            message = refresh_resolution_message(freshness)
            if message and refresh_status_blocks_resolution(freshness):
                return message
    suffix = f" from registry {registry}" if registry else ""
    version_suffix = f"@{version}" if version else ""
    return f"No matching skill source found for {name}{version_suffix}{suffix}."


def _decorate_resolution(
    resolved: dict[str, Any], *, reason: str | None, snapshot: str | None
) -> dict[str, Any]:
    payload = dict(resolved)
    if payload.get("source_type") == "distribution-manifest":
        if reason is not None:
            reason = {
                "active-default": "distribution-active-default",
                "exact-version": "distribution-exact-version",
                "archived-exact-snapshot": "distribution-archived-exact-version",
            }.get(reason, reason)
    elif snapshot:
        reason = f"registry-snapshot-{reason}"
    payload["resolution_reason"] = reason
    return payload


def resolve_source_candidate(
    name: str,
    *,
    version: str | None = None,
    allow_incubating: bool = False,
    registry: str | None = None,
    snapshot: str | None = None,
) -> dict[str, Any]:
    if snapshot and not registry:
        raise SourceResolutionError("--snapshot requires --registry")

    requested_publisher, requested_name = parse_requested_skill(name)
    if not requested_name:
        raise SourceResolutionError("skill name must be non-empty")
    cfg, loaded_candidates, blocked = load_candidates(registry, snapshot=snapshot)
    candidates = matching_candidates(
        loaded_candidates,
        requested_name=requested_name,
        requested_publisher=requested_publisher,
        requested_identity=name,
        allow_incubating=allow_incubating,
    )
    resolved, reason = select_candidate(
        candidates,
        requested_name=requested_name,
        requested_identity=name,
        requested_publisher=requested_publisher,
        version=version,
    )

    if resolved is None:
        raise SourceResolutionError(
            _resolution_failure_message(
                cfg=cfg,
                blocked=blocked,
                registry=registry,
                name=name,
                version=version,
            )
        )
    return _decorate_resolution(resolved, reason=reason, snapshot=snapshot)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--version")
    ap.add_argument("--allow-incubating", action="store_true")
    ap.add_argument("--registry")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--snapshot")
    args = ap.parse_args(argv)

    try:
        resolved = resolve_source_candidate(
            args.name,
            version=args.version,
            allow_incubating=args.allow_incubating,
            registry=args.registry,
            snapshot=args.snapshot,
        )
    except SourceResolutionError as exc:
        ap.error(str(exc))
    if args.json:
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
    else:
        print(resolved["path"])
    return 0


if __name__ == "__main__":
    main()
