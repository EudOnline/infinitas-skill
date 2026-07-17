"""Composition of individual signing doctor checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from infinitas_skill.release.signing_doctor import (
    parse_signing_doctor_args,
    render_signing_doctor_report,
)
from infinitas_skill.release.state import ROOT, ReleaseError, collect_release_state, resolve_skill


def _failed_config_report(checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "overall_status": "fail",
        "skill": None,
        "expected_provenance": None,
        "inferred_signer_identities": [],
        "checks": checks,
    }


def signing_doctor_main(argv: list[str] | None = None) -> int:
    args = parse_signing_doctor_args(argv)
    report = build_signing_doctor_report(
        skill=args.skill,
        identity=args.identity,
        provenance=args.provenance,
        root=ROOT,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_signing_doctor_report(report))
    return 1 if report["overall_status"] == "fail" else 0


def _relative_or_absolute(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


def build_signing_doctor_report(
    *,
    skill: str | None,
    identity: str | None,
    provenance: str | None,
    root: Path,
) -> dict[str, Any]:
    from infinitas_skill.release.signing_doctor import (
        _check_allowed_signers,
        _check_attestation,
        _check_git_gpg_format,
        _check_namespace_releaser_policy,
        _check_namespace_signer_policy,
        _check_release_preflight,
        _check_release_tag,
        _check_signing_config,
        _check_signing_key,
        make_check,
        summarize_overall,
    )

    checks: list[dict[str, Any]] = []
    skill_dir: Path | None = None
    expected_provenance: Path | None = None
    signing, config_checks = _check_signing_config(root)
    if config_checks:
        return _failed_config_report(config_checks)
    allowed_entries, signer_checks = _check_allowed_signers(signing or {}, identity)
    checks.extend(signer_checks)
    inferred, key_checks = _check_signing_key(signing or {}, allowed_entries, identity, root)
    checks.extend(key_checks)
    checks.extend(_check_git_gpg_format(root))
    if skill:
        try:
            skill_dir = resolve_skill(root, skill)
            state = collect_release_state(skill_dir, mode="preflight", root=root)
        except ReleaseError as exc:
            checks.append(
                make_check(
                    "release-preflight",
                    "fail",
                    f"Cannot resolve release state for {skill}",
                    detail=str(exc),
                )
            )
        else:
            meta = state.get("skill") or {}
            candidate = (
                root / "catalog" / "provenance" / f"{meta.get('name')}-{meta.get('version')}.json"
            )
            has_artifact = (
                Path(provenance).expanduser().resolve().exists()
                if provenance
                else candidate.exists()
            )
            expected_provenance, preflight = _check_release_preflight(
                state, skill_dir.name, has_artifact, root
            )
            checks.extend(preflight)
            checks.extend(_check_namespace_signer_policy(state, meta.get("publisher"), inferred))
            checks.extend(_check_namespace_releaser_policy(state, meta.get("publisher"), root))
            checks.extend(_check_release_tag(state, skill_dir.name))
    provenance_path = Path(provenance).resolve() if provenance else expected_provenance
    checks.extend(_check_attestation(provenance_path, provenance, identity, root))
    return {
        "overall_status": summarize_overall(checks),
        "skill": str(skill_dir.relative_to(root)) if skill_dir else None,
        "expected_provenance": _relative_or_absolute(provenance_path, root),
        "inferred_signer_identities": inferred,
        "checks": checks,
    }
