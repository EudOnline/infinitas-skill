"""Attestation and provenance verification helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from infinitas_skill.policy.policy_pack import (
    PolicyPackError,
    load_effective_policy_domain,
)
from infinitas_skill.release.state import ROOT, signer_entries, signing_key_path
from infinitas_skill.release.transparency_log import (
    TransparencyLogError,
    build_transparency_log_request,
    resolve_transparency_log_entry_path,
    submit_transparency_log_entry,
    summarize_transparency_log_state,
)
from infinitas_skill.release.transparency_log import (
    write_json as write_transparency_log_json,
)


class AttestationError(Exception):
    pass


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_attestation_config(root=None):
    root = Path(root or ROOT).resolve()
    try:
        config = load_effective_policy_domain(root, "signing")
    except PolicyPackError as exc:
        raise AttestationError("; ".join(exc.errors)) from exc
    git_tag = config.get("git_tag") if isinstance(config.get("git_tag"), dict) else {}
    attestation = config.get("attestation") if isinstance(config.get("attestation"), dict) else {}
    ci = attestation.get("ci") if isinstance(attestation.get("ci"), dict) else {}
    transparency_log = (
        attestation.get("transparency_log")
        if isinstance(attestation.get("transparency_log"), dict)
        else {}
    )
    policy = attestation.get("policy") if isinstance(attestation.get("policy"), dict) else {}
    mode = policy.get("mode", "enforce")
    release_trust_mode = policy.get("release_trust_mode", "ssh")
    if release_trust_mode not in {"ssh", "ci", "both"}:
        raise AttestationError(
            "attestation.policy.release_trust_mode must be one of "
            f"'ssh', 'ci', or 'both', got {release_trust_mode!r}"
        )
    transparency_mode = transparency_log.get("mode", "disabled")
    if transparency_mode not in {"disabled", "advisory", "required"}:
        raise AttestationError(
            "attestation.transparency_log.mode must be one of 'disabled', 'advisory', or 'required'"
        )
    transparency_endpoint = transparency_log.get("endpoint")
    if transparency_endpoint is not None and (
        not isinstance(transparency_endpoint, str) or not transparency_endpoint.strip()
    ):
        raise AttestationError(
            "attestation.transparency_log.endpoint must be a non-empty string when present"
        )
    timeout_seconds = transparency_log.get("timeout_seconds", 5)
    if not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise AttestationError(
            "attestation.transparency_log.timeout_seconds must be a positive integer"
        )
    allowed_rel = (
        attestation.get("allowed_signers")
        or config.get("allowed_signers")
        or "config/allowed_signers"
    )
    namespace = attestation.get("namespace") or config.get("namespace") or "infinitas-skill"
    signature_ext = attestation.get("signature_ext") or config.get("signature_ext") or ".ssig"
    return {
        "config": config,
        "format": attestation.get("format", "ssh"),
        "namespace": namespace,
        "allowed_signers_rel": allowed_rel,
        "allowed_signers_path": (root / allowed_rel).resolve(),
        "signature_ext": signature_ext,
        "signing_key_env": attestation.get("signing_key_env")
        or git_tag.get("signing_key_env")
        or "INFINITAS_SKILL_GIT_SIGNING_KEY",
        "policy_mode": mode,
        "release_trust_mode": release_trust_mode,
        "requires_ssh_attestation": release_trust_mode in {"ssh", "both"},
        "requires_ci_attestation": release_trust_mode in {"ci", "both"},
        "ci": {
            "provider": ci.get("provider"),
            "issuer": ci.get("issuer"),
            "repository": ci.get("repository"),
            "workflow": ci.get("workflow"),
        },
        "transparency_log": {
            "mode": transparency_mode,
            "endpoint": transparency_endpoint.strip()
            if isinstance(transparency_endpoint, str)
            else None,
            "timeout_seconds": timeout_seconds,
        },
        "require_release_output": bool(
            policy.get("require_verified_attestation_for_release_output", mode == "enforce")
        ),
        "require_distribution": bool(
            policy.get("require_verified_attestation_for_distribution", mode == "enforce")
        ),
    }


def signature_path_for(provenance_path, config=None):
    path = Path(provenance_path)
    cfg = config or load_attestation_config(path.parent.parent.parent if path.name else ROOT)
    return path.with_suffix(path.suffix + cfg["signature_ext"])


def require_trusted_signers(config):
    entries = signer_entries(config["allowed_signers_path"])
    if not entries:
        raise AttestationError(
            f"{config['allowed_signers_rel']} has no signer entries; "
            "add trusted release signers before writing or verifying "
            "stable attestations"
        )
    return entries


def resolve_attestation_signer(identity=None, release_state=None):
    signer = identity
    if not signer and release_state:
        signer = ((release_state.get("git") or {}).get("local_tag") or {}).get("signer")
    if not signer:
        raise AttestationError(
            "cannot determine attestation signer identity; pass --signer "
            "or verify the release tag against repo-managed allowed "
            "signers first"
        )
    return signer


def resolve_attestation_key(root=None, config=None, override=None):
    if override:
        return override
    root = Path(root or ROOT).resolve()
    cfg = config or load_attestation_config(root)
    value = signing_key_path(root, {"signing_key_env": cfg["signing_key_env"]})
    if not value:
        raise AttestationError(
            "stable release attestations require an SSH signing key; "
            f"set {cfg['signing_key_env']} or git config user.signingkey"
        )
    return value


def publish_attestation_to_transparency_log(provenance_path, root=None):
    root = Path(root or ROOT).resolve()
    provenance_path = Path(provenance_path).resolve()
    cfg = load_attestation_config(root)
    transparency_cfg = cfg.get("transparency_log") or {}
    mode = transparency_cfg.get("mode", "disabled")
    if mode == "disabled":
        return {
            "mode": mode,
            "published": False,
            "entry": None,
            "error": None,
        }

    endpoint = transparency_cfg.get("endpoint")
    if not endpoint:
        message = "transparency log endpoint is not configured"
        if mode == "required":
            raise AttestationError(message)
        return {
            "mode": mode,
            "published": False,
            "entry": None,
            "error": message,
        }

    payload = load_json(provenance_path)
    errors = validate_provenance_payload(payload)
    if errors:
        raise AttestationError("; ".join(errors))

    request_payload = build_transparency_log_request(provenance_path, payload=payload)
    try:
        entry = submit_transparency_log_entry(
            endpoint,
            request_payload,
            timeout_seconds=transparency_cfg.get("timeout_seconds", 5),
        )
    except TransparencyLogError as exc:
        if mode == "required":
            raise AttestationError(str(exc)) from exc
        return {
            "mode": mode,
            "published": False,
            "entry": None,
            "error": str(exc),
        }

    return {
        "mode": mode,
        "published": True,
        "entry": entry,
        "error": None,
    }


def record_attestation_transparency_log(provenance_path, root=None, entry_path=None):
    root = Path(root or ROOT).resolve()
    provenance_path = Path(provenance_path).resolve()
    payload = load_json(provenance_path)
    descriptor = (
        payload.get("transparency_log") if isinstance(payload.get("transparency_log"), dict) else {}
    )
    target_path = (
        Path(entry_path).resolve()
        if entry_path
        else resolve_transparency_log_entry_path(
            provenance_path,
            descriptor=descriptor,
            root=root,
        )
    )

    result = publish_attestation_to_transparency_log(provenance_path, root=root)
    result["entry_path"] = (
        str(target_path.relative_to(root)) if target_path.is_relative_to(root) else str(target_path)
    )
    if result.get("published"):
        write_transparency_log_json(target_path, result.get("entry"))
    return result


def validate_provenance_payload(payload):
    errors = []

    def require_string(mapping, key, label):
        value = mapping.get(key) if isinstance(mapping, dict) else None
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} must be a non-empty string")
        return value

    release = payload.get("release")
    release_mode = "stable-release"
    if isinstance(release, dict):
        if release.get("release_mode") is not None:
            if release.get("release_mode") not in {"stable-release", "local-tag"}:
                errors.append(
                    "release.release_mode must be 'stable-release' or 'local-tag' when present"
                )
            else:
                release_mode = release.get("release_mode")

    if payload.get("kind") != "skill-release-attestation":
        errors.append("kind must be skill-release-attestation")
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    skill = payload.get("skill")
    if not isinstance(skill, dict):
        errors.append("skill must be an object")
    else:
        require_string(skill, "name", "skill.name")
        require_string(skill, "version", "skill.version")
        require_string(skill, "path", "skill.path")
        for key in ["owners", "maintainers"]:
            value = skill.get(key)
            if value is not None and not isinstance(value, list):
                errors.append(f"skill.{key} must be an array when present")

    git = payload.get("git")
    if not isinstance(git, dict):
        errors.append("git must be an object")
    else:
        require_string(git, "commit", "git.commit")
        require_string(git, "expected_tag", "git.expected_tag")
        require_string(git, "release_ref", "git.release_ref")
        if git.get("signed_tag_verified") is not True:
            errors.append("git.signed_tag_verified must be true")

    source_snapshot = payload.get("source_snapshot")
    if not isinstance(source_snapshot, dict):
        errors.append("source_snapshot must be an object")
    else:
        require_string(source_snapshot, "tag", "source_snapshot.tag")
        require_string(source_snapshot, "ref", "source_snapshot.ref")
        require_string(source_snapshot, "commit", "source_snapshot.commit")
        if source_snapshot.get("immutable") is not True:
            errors.append("source_snapshot.immutable must be true")
        pushed = source_snapshot.get("pushed")
        if not isinstance(pushed, bool):
            errors.append("source_snapshot.pushed must be boolean")
        elif release_mode == "stable-release" and pushed is not True:
            errors.append("source_snapshot.pushed must be true for stable-release attestations")
        elif release_mode == "local-tag" and pushed is not False:
            errors.append("source_snapshot.pushed must be false for local-tag attestations")

    registry = payload.get("registry")
    if not isinstance(registry, dict):
        errors.append("registry must be an object")
    else:
        if not isinstance(registry.get("registries_consulted"), list):
            errors.append("registry.registries_consulted must be an array")
        if not isinstance(registry.get("resolved"), list):
            errors.append("registry.resolved must be an array")

    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, dict):
        errors.append("dependencies must be an object")
    else:
        if not isinstance(dependencies.get("steps"), list):
            errors.append("dependencies.steps must be an array")
        if not isinstance(dependencies.get("registries_consulted"), list):
            errors.append("dependencies.registries_consulted must be an array")

    review = payload.get("review")
    if not isinstance(review, dict):
        errors.append("review must be an object")
    else:
        if not isinstance(review.get("reviewers"), list):
            errors.append("review.reviewers must be an array")

    if not isinstance(release, dict):
        errors.append("release must be an object")
    else:
        releaser_identity = release.get("releaser_identity")
        if releaser_identity is not None and (
            not isinstance(releaser_identity, str) or not releaser_identity.strip()
        ):
            errors.append("release.releaser_identity must be a non-empty string when present")
        if not isinstance(release.get("transfer_required"), bool):
            errors.append("release.transfer_required must be boolean")
        if not isinstance(release.get("transfer_authorized"), bool):
            errors.append("release.transfer_authorized must be boolean")
        for key in [
            "authorized_signers",
            "authorized_releasers",
            "transfer_matches",
            "competing_claims",
        ]:
            if not isinstance(release.get(key), list):
                errors.append(f"release.{key} must be an array")

    attestation = payload.get("attestation")
    if not isinstance(attestation, dict):
        errors.append("attestation must be an object")
    else:
        attestation_format = attestation.get("format")
        if attestation_format not in {"ssh", "ci"}:
            errors.append("attestation.format must be ssh or ci")
        if attestation.get("policy_mode") not in {"advisory", "enforce"}:
            errors.append("attestation.policy_mode must be advisory or enforce")
        if not isinstance(attestation.get("require_verified_attestation_for_release_output"), bool):
            errors.append(
                "attestation.require_verified_attestation_for_release_output must be boolean"
            )
        if not isinstance(attestation.get("require_verified_attestation_for_distribution"), bool):
            errors.append(
                "attestation.require_verified_attestation_for_distribution must be boolean"
            )
        if attestation_format == "ssh":
            require_string(attestation, "namespace", "attestation.namespace")
            require_string(attestation, "allowed_signers", "attestation.allowed_signers")
            require_string(attestation, "signature_file", "attestation.signature_file")
            require_string(attestation, "signature_ext", "attestation.signature_ext")
            require_string(attestation, "signer_identity", "attestation.signer_identity")
        if attestation_format == "ci":
            require_string(attestation, "generator", "attestation.generator")

    ci = payload.get("ci")
    if attestation and attestation.get("format") == "ci":
        if not isinstance(ci, dict):
            errors.append("ci must be an object for CI attestations")
        else:
            for key in [
                "provider",
                "repository",
                "workflow",
                "run_id",
                "run_attempt",
                "sha",
                "ref",
            ]:
                require_string(ci, key, f"ci.{key}")

    distribution = payload.get("distribution")
    if distribution is not None:
        if not isinstance(distribution, dict):
            errors.append("distribution must be an object when present")
        else:
            manifest_path = distribution.get("manifest_path")
            if manifest_path is not None and (
                not isinstance(manifest_path, str) or not manifest_path.strip()
            ):
                errors.append("distribution.manifest_path must be a non-empty string when present")
            bundle = distribution.get("bundle")
            if not isinstance(bundle, dict):
                errors.append("distribution.bundle must be an object")
            else:
                require_string(bundle, "path", "distribution.bundle.path")
                if bundle.get("format") != "tar.gz":
                    errors.append("distribution.bundle.format must be tar.gz")
                require_string(bundle, "sha256", "distribution.bundle.sha256")
                require_string(bundle, "root_dir", "distribution.bundle.root_dir")
                if not isinstance(bundle.get("size"), int) or bundle.get("size") < 0:
                    errors.append("distribution.bundle.size must be a non-negative integer")
                if not isinstance(bundle.get("file_count"), int) or bundle.get("file_count") < 1:
                    errors.append("distribution.bundle.file_count must be a positive integer")

    return errors


def _combined_output(result):
    parts = []
    if result.stdout:
        parts.append(result.stdout.strip())
    if result.stderr:
        parts.append(result.stderr.strip())
    return "\n".join(part for part in parts if part).strip()


def _verify_ssh_attestation(
    provenance_path, payload, cfg, identity=None, allowed_signers=None, namespace=None, root=None
):
    root = Path(root or ROOT).resolve()
    provenance_path = Path(provenance_path).resolve()
    attestation = payload["attestation"]
    identity = identity or attestation.get("signer_identity")
    expected_allowed_rel = cfg["allowed_signers_rel"]
    expected_namespace = cfg["namespace"]
    if allowed_signers:
        allowed_path = Path(allowed_signers)
        if not allowed_path.is_absolute():
            allowed_path = (root / allowed_path).resolve()
    else:
        if attestation.get("allowed_signers") != expected_allowed_rel:
            raise AttestationError(
                "attestation allowed_signers "
                f"{attestation.get('allowed_signers')!r} does not match "
                f"repo-managed {expected_allowed_rel!r}"
            )
        allowed_path = cfg["allowed_signers_path"]
    if namespace:
        verify_namespace = namespace
    else:
        if attestation.get("namespace") != expected_namespace:
            raise AttestationError(
                "attestation namespace "
                f"{attestation.get('namespace')!r} does not match "
                f"repo-managed {expected_namespace!r}"
            )
        verify_namespace = expected_namespace

    require_trusted_signers(
        {
            "allowed_signers_rel": str(allowed_path.relative_to(root))
            if allowed_path.is_relative_to(root)
            else str(allowed_path),
            "allowed_signers_path": allowed_path,
        }
    )

    signature_file = attestation.get("signature_file")
    signature_path = Path(signature_file)
    if not signature_path.is_absolute():
        signature_path = (provenance_path.parent / signature_path).resolve()
    if not signature_path.exists():
        raise AttestationError(f"missing SSH attestation signature: {signature_path}")

    result = subprocess.run(
        [
            "ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(allowed_path),
            "-I",
            identity,
            "-n",
            verify_namespace,
            "-s",
            str(signature_path),
        ],
        input=provenance_path.read_text(encoding="utf-8"),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AttestationError(_combined_output(result) or "SSH attestation verification failed")
    return {
        "verified": True,
        "skill": payload.get("skill", {}).get("name"),
        "version": payload.get("skill", {}).get("version"),
        "identity": identity,
        "namespace": verify_namespace,
        "allowed_signers": str(allowed_path),
        "signature_path": str(signature_path),
        "output": _combined_output(result),
        "format": "ssh",
    }


def verify_ci_attestation(provenance_path, root=None):
    root = Path(root or ROOT).resolve()
    provenance_path = Path(provenance_path).resolve()
    try:
        payload = load_json(provenance_path)
    except Exception as exc:
        raise AttestationError(
            f"could not parse attestation payload {provenance_path}: {exc}"
        ) from exc

    errors = validate_provenance_payload(payload)
    if errors:
        raise AttestationError("; ".join(errors))

    attestation = payload["attestation"]
    if attestation.get("format") != "ci":
        raise AttestationError(f"expected CI attestation format, got {attestation.get('format')!r}")

    cfg = load_attestation_config(root)
    ci_cfg = cfg.get("ci") or {}
    ci = payload.get("ci") or {}
    for key in ["provider", "repository", "workflow"]:
        expected = ci_cfg.get(key)
        actual = ci.get(key)
        if expected and actual != expected:
            raise AttestationError(f"ci.{key} {actual!r} does not match repo-managed {expected!r}")
    if ci.get("sha") != payload.get("git", {}).get("commit"):
        raise AttestationError("ci.sha does not match git.commit")
    if ci.get("sha") != payload.get("source_snapshot", {}).get("commit"):
        raise AttestationError("ci.sha does not match source_snapshot.commit")
    if ci.get("ref") != payload.get("source_snapshot", {}).get("ref"):
        raise AttestationError("ci.ref does not match source_snapshot.ref")

    return {
        "verified": True,
        "skill": payload.get("skill", {}).get("name"),
        "version": payload.get("skill", {}).get("version"),
        "provider": ci.get("provider"),
        "repository": ci.get("repository"),
        "workflow": ci.get("workflow"),
        "run_id": ci.get("run_id"),
        "sha": ci.get("sha"),
        "ref": ci.get("ref"),
        "format": "ci",
    }


def _companion_ci_path(provenance_path):
    return provenance_path.with_name(f"{provenance_path.stem}.ci.json")


def _companion_ssh_path(provenance_path):
    name = provenance_path.name
    if name.endswith(".ci.json"):
        return provenance_path.with_name(f"{name[:-8]}.json")
    raise AttestationError(f"cannot derive SSH companion path from {provenance_path}")


def _distribution_summary(payload):
    distribution = payload.get("distribution")
    if not isinstance(distribution, dict):
        return None

    summary = {}
    if isinstance(distribution.get("manifest_path"), str) and distribution.get("manifest_path"):
        summary["manifest_path"] = distribution.get("manifest_path")

    bundle = distribution.get("bundle")
    if isinstance(bundle, dict):
        if isinstance(bundle.get("path"), str) and bundle.get("path"):
            summary["bundle_path"] = bundle.get("path")
        if isinstance(bundle.get("sha256"), str) and bundle.get("sha256"):
            summary["bundle_sha256"] = bundle.get("sha256")
        if isinstance(bundle.get("size"), int):
            summary["bundle_size"] = bundle.get("size")
        if isinstance(bundle.get("file_count"), int):
            summary["bundle_file_count"] = bundle.get("file_count")

    file_manifest = distribution.get("file_manifest")
    if isinstance(file_manifest, list):
        summary["file_manifest_count"] = len(file_manifest)

    build = distribution.get("build")
    if isinstance(build, dict):
        summary["build"] = build

    return summary or None


def verify_attestation(
    provenance_path, identity=None, allowed_signers=None, namespace=None, root=None
):
    root = Path(root or ROOT).resolve()
    provenance_path = Path(provenance_path).resolve()
    try:
        payload = load_json(provenance_path)
    except Exception as exc:
        raise AttestationError(
            f"could not parse attestation payload {provenance_path}: {exc}"
        ) from exc

    errors = validate_provenance_payload(payload)
    if errors:
        raise AttestationError("; ".join(errors))

    cfg = load_attestation_config(root)
    attestation = payload["attestation"]
    formats_verified = []
    if attestation.get("format") == "ci":
        result = verify_ci_attestation(provenance_path, root=root)
        formats_verified.append("ci")
        if cfg["requires_ssh_attestation"]:
            ssh_path = _companion_ssh_path(provenance_path)
            if not ssh_path.exists():
                raise AttestationError(f"missing required SSH attestation companion: {ssh_path}")
            _verify_ssh_attestation(
                ssh_path,
                load_json(ssh_path),
                cfg,
                identity=identity,
                allowed_signers=allowed_signers,
                namespace=namespace,
                root=root,
            )
            formats_verified.append("ssh")
    else:
        result = _verify_ssh_attestation(
            provenance_path,
            payload,
            cfg,
            identity=identity,
            allowed_signers=allowed_signers,
            namespace=namespace,
            root=root,
        )
        formats_verified.append("ssh")
        if cfg["requires_ci_attestation"]:
            ci_path = _companion_ci_path(provenance_path)
            if not ci_path.exists():
                raise AttestationError(f"missing required CI attestation companion: {ci_path}")
            verify_ci_attestation(ci_path, root=root)
            formats_verified.append("ci")

    result["formats_verified"] = formats_verified
    result["policy_mode"] = cfg["release_trust_mode"]
    distribution = _distribution_summary(payload)
    if distribution:
        result["distribution"] = distribution
    try:
        transparency_log = summarize_transparency_log_state(
            provenance_path, payload=payload, root=root
        )
    except TransparencyLogError as exc:
        raise AttestationError(str(exc)) from exc
    if transparency_log:
        if transparency_log.get("required") and not transparency_log.get("verified"):
            raise AttestationError("required transparency log proof is missing or unverified")
        result["transparency_log"] = transparency_log
    return result


__all__ = [
    "AttestationError",
    "load_json",
    "load_attestation_config",
    "signature_path_for",
    "require_trusted_signers",
    "resolve_attestation_signer",
    "resolve_attestation_key",
    "publish_attestation_to_transparency_log",
    "record_attestation_transparency_log",
    "validate_provenance_payload",
    "verify_ci_attestation",
    "verify_attestation",
]
