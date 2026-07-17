"""Clean release orchestration for tags, attestations, and distributions."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from infinitas_skill.install.distribution import deterministic_bundle, distribution_paths
from infinitas_skill.install.distribution_materialization import (
    build_distribution_manifest_payload,
)
from infinitas_skill.install.distribution_verification import verify_distribution_manifest
from infinitas_skill.install.skill_validation import validate_installable_skill_dir
from infinitas_skill.registry.catalog import run_registry_catalog_build
from infinitas_skill.release.attestation import (
    load_attestation_config,
    record_attestation_transparency_log,
    resolve_attestation_key,
    resolve_attestation_signer,
    verify_attestation,
)
from infinitas_skill.release.provenance_payload import (
    build_common_payload,
    build_distribution_payload,
    build_transparency_log_payload,
    collect_release_context,
)
from infinitas_skill.release.release_resolution import resolve_skill
from infinitas_skill.release.tagging import tag_skill_release
from infinitas_skill.release.trust_cli import sign_attestation_file


class ReleasePublishError(Exception):
    pass


def _release_metadata(skill_dir: Path) -> tuple[dict[str, Any], str]:
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    changelog = (skill_dir / "CHANGELOG.md").read_text(encoding="utf-8")
    version = str(meta.get("version"))
    match = re.search(
        rf"^##\s+{re.escape(version)}\s+-.*?(?=^##\s+|\Z)",
        changelog,
        re.MULTILINE | re.DOTALL,
    )
    notes = match.group(0).strip() if match else f"## {version}\n\n- No changelog entry."
    return meta, notes


def _source_notes(context: dict[str, Any], notes: str) -> str:
    state = context["state"]
    git = state["git"]
    remote = git["remote_tag"].get("name") or "origin"
    commit = (
        git["remote_tag"].get("target_commit")
        or git["local_tag"].get("target_commit")
        or git["head_commit"]
    )
    lines = [
        notes.rstrip(),
        "",
        "## Source Snapshot",
        "",
        f"- Tag: `{git['expected_tag']}`",
        f"- Ref: `refs/tags/{git['expected_tag']}`",
        f"- Commit: `{commit}`",
        f"- Upstream: `{git['upstream']}`",
        f"- Remote: `{remote}`",
    ]
    signer = git["local_tag"].get("signer")
    if signer:
        lines.append(f"- Verified signer: `{signer}`")
    return "\n".join(lines) + "\n"


def _attestation_payload(
    *,
    context: dict[str, Any],
    config: dict[str, Any],
    output_name: str,
    signer: str,
    distribution_args: SimpleNamespace,
) -> dict[str, Any]:
    payload = build_common_payload(context)
    payload["attestation"] = {
        "format": config["format"],
        "namespace": config["namespace"],
        "allowed_signers": config["allowed_signers_rel"],
        "signature_file": f"{output_name}{config['signature_ext']}",
        "signature_ext": config["signature_ext"],
        "signer_identity": signer,
        "policy_mode": config["policy_mode"],
        "require_verified_attestation_for_release_output": config["require_release_output"],
        "require_verified_attestation_for_distribution": config["require_distribution"],
    }
    payload["distribution"] = build_distribution_payload(distribution_args)
    transparency = build_transparency_log_payload(distribution_args, config)
    if transparency:
        payload["transparency_log"] = transparency
    return payload


def _write_attested_distribution(
    *,
    root: Path,
    skill_dir: Path,
    context: dict[str, Any],
    meta: dict[str, Any],
    signer: str | None,
    releaser: str | None,
    ssh_key: str | None,
) -> dict[str, Any]:
    publisher = meta.get("publisher")
    if not isinstance(publisher, str) or not publisher:
        raise ReleasePublishError("publisher is required for release distributions")
    name = str(meta["name"])
    version = str(meta["version"])
    paths = distribution_paths(root, name, version, publisher=publisher)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    staged_bundle = paths["bundle"].with_suffix(paths["bundle"].suffix + ".tmp")
    bundle = deterministic_bundle(skill_dir, staged_bundle)
    provenance = root / "catalog" / "provenance" / f"{name}-{version}.json"
    provenance.parent.mkdir(parents=True, exist_ok=True)
    transparency = provenance.with_name(f"{name}-{version}.transparency.json")
    config = load_attestation_config(root)
    selected_signer = resolve_attestation_signer(signer, context["state"])
    selected_key = resolve_attestation_key(root, config=config, override=ssh_key)
    context["generated_at"] = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    context["releaser_identity"] = releaser or context["releaser_identity"]
    distribution_args = SimpleNamespace(
        distribution_manifest_path=str(paths["manifest_rel"]),
        distribution_bundle_path=str(paths["bundle_rel"]),
        distribution_bundle_source_path=str(staged_bundle),
        distribution_bundle_sha256=bundle["sha256"],
        distribution_bundle_size=bundle["size"],
        distribution_bundle_root_dir=bundle["root_dir"],
        distribution_bundle_file_count=bundle["file_count"],
        transparency_log_entry_path=str(transparency.relative_to(root)),
    )
    payload = _attestation_payload(
        context=context,
        config=config,
        output_name=provenance.name,
        signer=selected_signer,
        distribution_args=distribution_args,
    )
    provenance.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    signature = sign_attestation_file(provenance, key=selected_key, root=root)
    record_attestation_transparency_log(provenance, root=root, entry_path=transparency)
    verify_attestation(provenance, identity=selected_signer, root=root)
    staged_bundle.replace(paths["bundle"])
    manifest = build_distribution_manifest_payload(
        provenance,
        paths["bundle"],
        root=root,
        attestation_root=root,
    )
    paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    verify_distribution_manifest(paths["manifest"], root=root, attestation_root=root)
    run_registry_catalog_build(root=root)
    return {
        "provenance": str(provenance),
        "signature": str(signature),
        "bundle": str(paths["bundle"]),
        "manifest": str(paths["manifest"]),
    }


def publish_skill_release(
    *,
    root: str | Path,
    skill: str,
    preview: bool = False,
    create_tag: bool = False,
    push_tag: bool = False,
    unsigned_tag: bool = False,
    notes_out: str | None = None,
    write_attestation: bool = False,
    github_release: bool = False,
    signer: str | None = None,
    releaser: str | None = None,
    ssh_key: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    skill_dir = resolve_skill(repo_root, skill)
    validate_installable_skill_dir(skill_dir, repo_root=repo_root)
    meta, raw_notes = _release_metadata(skill_dir)
    if meta.get("status") != "active":
        raise ReleasePublishError(f"release requires active status, got {meta.get('status')}")
    if preview:
        if create_tag or push_tag or write_attestation or github_release:
            raise ReleasePublishError("preview cannot be combined with release mutations")
        if notes_out:
            Path(notes_out).write_text(raw_notes + "\n", encoding="utf-8")
        return {"ok": True, "state": "preview", "notes": raw_notes, "skill": meta["name"]}
    if unsigned_tag and (push_tag or write_attestation or github_release):
        raise ReleasePublishError("stable release output requires a signed tag")

    tag_result = tag_skill_release(
        root=repo_root,
        skill=str(skill_dir),
        create=create_tag or push_tag,
        push=push_tag,
        unsigned=unsigned_tag,
        releaser=releaser,
    )
    release_mode = "stable-release" if push_tag else "local-tag"
    context = collect_release_context(
        skill_dir,
        root=repo_root,
        releaser=releaser,
        release_mode=release_mode,
    )
    notes = _source_notes(context, raw_notes)
    if notes_out:
        Path(notes_out).write_text(notes, encoding="utf-8")
    artifacts = None
    if write_attestation:
        artifacts = _write_attested_distribution(
            root=repo_root,
            skill_dir=skill_dir,
            context=context,
            meta=meta,
            signer=signer,
            releaser=releaser,
            ssh_key=ssh_key,
        )
    if github_release:
        result = subprocess.run(
            [
                "gh",
                "release",
                "create",
                tag_result["tag"],
                "--title",
                tag_result["tag"],
                "--notes",
                notes,
            ],
            cwd=repo_root,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise ReleasePublishError((result.stderr or result.stdout).strip())
    return {
        "ok": True,
        "state": "released",
        "skill": meta.get("qualified_name") or meta.get("name"),
        "version": meta.get("version"),
        "tag": tag_result,
        "notes_path": notes_out,
        "artifacts": artifacts,
        "verified_attestation": bool(artifacts),
    }


def configure_release_publish_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("skill")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--create-tag", action="store_true")
    parser.add_argument("--push-tag", action="store_true")
    parser.add_argument("--unsigned-tag", action="store_true")
    parser.add_argument("--notes-out")
    parser.add_argument("--write-attestation", action="store_true")
    parser.add_argument("--github-release", action="store_true")
    parser.add_argument("--signer")
    parser.add_argument("--releaser")
    parser.add_argument("--ssh-key")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    return parser


__all__ = [
    "ReleasePublishError",
    "configure_release_publish_parser",
    "publish_skill_release",
]
