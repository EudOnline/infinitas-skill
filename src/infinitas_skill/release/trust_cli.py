"""Release attestation generation, signing, and verification commands."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from infinitas_skill.install.distribution_core import DistributionError
from infinitas_skill.install.distribution_materialization import (
    build_distribution_manifest_payload,
)
from infinitas_skill.release.attestation import (
    AttestationError,
    load_attestation_config,
    verify_attestation,
    verify_ci_attestation,
)
from infinitas_skill.release.provenance_payload import (
    build_common_payload,
    build_distribution_payload,
    collect_release_context,
)
from infinitas_skill.release.state import ReleaseError


def _emit(payload: dict, *, as_json: bool = True) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if as_json else None))
    return 0


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required for CI attestation generation")
    return value


def _ci_metadata() -> dict:
    repository = _required_env("GITHUB_REPOSITORY")
    run_id = _required_env("GITHUB_RUN_ID")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    return {
        "provider": "github-actions",
        "repository": repository,
        "workflow": _required_env("GITHUB_WORKFLOW"),
        "run_id": run_id,
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
        "sha": _required_env("GITHUB_SHA"),
        "ref": _required_env("GITHUB_REF"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
        "url": f"{server_url}/{repository}/actions/runs/{run_id}",
    }


def run_generate_ci_attestation(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    try:
        context = collect_release_context(
            args.skill,
            root=root,
            releaser=args.releaser,
            ignore_errors=[
                "worktree is dirty",
                "has no upstream",
                "branch is ahead of",
                "branch is behind",
            ],
        )
        config = load_attestation_config(root)
        context["generated_at"] = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        output_name = args.output_name or (
            f"{context['meta'].get('name')}-{context['meta'].get('version')}.ci.json"
        )
        payload = build_common_payload(context)
        payload["attestation"] = {
            "format": "ci",
            "generator": "github-actions",
            "output_name": output_name,
            "policy_mode": config["policy_mode"],
            "require_verified_attestation_for_release_output": config["require_release_output"],
            "require_verified_attestation_for_distribution": config["require_distribution"],
        }
        payload["ci"] = _ci_metadata()
        distribution = build_distribution_payload(args)
        if distribution:
            payload["distribution"] = distribution
    except (AttestationError, ReleaseError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return _emit(payload)


def run_generate_distribution_manifest(args: argparse.Namespace) -> int:
    root = Path(args.repo_root).resolve()
    try:
        payload = build_distribution_manifest_payload(
            args.provenance,
            args.bundle,
            root=root,
            attestation_root=root,
        )
    except DistributionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


def run_sign_attestation(args: argparse.Namespace) -> int:
    try:
        signature_path = sign_attestation_file(
            args.provenance,
            key=args.key,
            root=args.repo_root,
            namespace=args.namespace,
        )
    except AttestationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(signature_path)
    return 0


def sign_attestation_file(
    provenance: str | Path,
    *,
    key: str,
    root: str | Path,
    namespace: str | None = None,
) -> Path:
    path = Path(provenance).resolve()
    config = load_attestation_config(Path(root).resolve())
    selected_namespace = namespace or config["namespace"]
    signature_path = path.with_suffix(path.suffix + config["signature_ext"])
    result = subprocess.run(
        ["ssh-keygen", "-Y", "sign", "-f", key, "-n", selected_namespace, str(path)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AttestationError((result.stderr or result.stdout).strip())
    generated = Path(f"{path}.sig")
    signature_path.unlink(missing_ok=True)
    shutil.move(str(generated), signature_path)
    return signature_path


def run_verify_attestation(args: argparse.Namespace) -> int:
    try:
        payload = verify_attestation(
            args.provenance,
            identity=args.identity,
            allowed_signers=args.allowed_signers,
            namespace=args.namespace,
            root=Path(args.repo_root).resolve(),
        )
    except AttestationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return _emit(payload, as_json=args.json)


def run_verify_ci_attestation(args: argparse.Namespace) -> int:
    try:
        payload = verify_ci_attestation(args.provenance, root=Path(args.repo_root).resolve())
    except AttestationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return _emit(payload, as_json=args.json)


def _add_root_and_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")


def configure_release_trust_commands(subparsers: argparse._SubParsersAction) -> None:
    ci = subparsers.add_parser("generate-ci-attestation", help="Generate CI attestation JSON")
    ci.add_argument("skill")
    ci.add_argument("--output-name")
    ci.add_argument("--releaser")
    ci.add_argument("--distribution-manifest-path")
    ci.add_argument("--distribution-bundle-path")
    ci.add_argument("--distribution-bundle-source-path")
    ci.add_argument("--distribution-bundle-sha256")
    ci.add_argument("--distribution-bundle-size", type=int)
    ci.add_argument("--distribution-bundle-root-dir")
    ci.add_argument("--distribution-bundle-file-count", type=int)
    ci.add_argument("--repo-root", default=".")
    ci.set_defaults(_handler=run_generate_ci_attestation)

    manifest = subparsers.add_parser(
        "generate-distribution-manifest",
        help="Generate a verified distribution manifest",
    )
    manifest.add_argument("--provenance", required=True)
    manifest.add_argument("--bundle", required=True)
    manifest.add_argument("--output")
    manifest.add_argument("--repo-root", default=".")
    manifest.set_defaults(_handler=run_generate_distribution_manifest)

    sign = subparsers.add_parser("sign-attestation", help="SSH-sign an attestation")
    sign.add_argument("provenance")
    sign.add_argument("--key", required=True)
    sign.add_argument("--namespace")
    sign.add_argument("--repo-root", default=".")
    sign.set_defaults(_handler=run_sign_attestation)

    verify = subparsers.add_parser("verify-attestation", help="Verify release attestation policy")
    verify.add_argument("provenance")
    verify.add_argument("--identity")
    verify.add_argument("--allowed-signers")
    verify.add_argument("--namespace")
    _add_root_and_json(verify)
    verify.set_defaults(_handler=run_verify_attestation)

    verify_ci = subparsers.add_parser("verify-ci-attestation", help="Verify CI attestation policy")
    verify_ci.add_argument("provenance")
    _add_root_and_json(verify_ci)
    verify_ci.set_defaults(_handler=run_verify_ci_attestation)


__all__ = ["configure_release_trust_commands", "sign_attestation_file"]
