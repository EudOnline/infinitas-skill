"""Signing bootstrap doctor flow for release operations."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from infinitas_skill.release.attestation import (
    AttestationError,
    load_attestation_config,
    verify_attestation,
)
from infinitas_skill.release.signing_bootstrap import (
    SigningBootstrapError,
    parse_allowed_signers,
    public_key_from_key_path,
    signer_identities_for_key,
)
from infinitas_skill.release.state import (
    ROOT,
    ReleaseError,
    collect_release_state,
    load_signing_config,
    resolve_releaser_identity,
    resolve_skill,
    signing_key_path,
)


def configure_signing_doctor_parser(
    parser: argparse.ArgumentParser,
) -> argparse.ArgumentParser:
    parser.description = (
        "Diagnose SSH signing bootstrap, release-tag readiness, and attestation prerequisites"
    )
    parser.add_argument("skill", nargs="?", help="Skill name or path to diagnose")
    parser.add_argument("--identity", help="Expected signer identity to use in fix suggestions")
    parser.add_argument("--provenance", help="Existing provenance JSON to verify")
    parser.add_argument("--json", action="store_true", help="Print machine-readable doctor output")
    return parser


def build_signing_doctor_parser(*, prog: str | None = None) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Diagnose SSH signing bootstrap, release-tag readiness, and attestation prerequisites"
        ),
    )
    return configure_signing_doctor_parser(parser)


def parse_signing_doctor_args(
    argv: list[str] | None = None,
    *,
    prog: str | None = None,
) -> argparse.Namespace:
    return build_signing_doctor_parser(prog=prog).parse_args(argv)


def make_check(check_id, status, summary, *, detail=None, fixes=None, data=None):
    return {
        "id": check_id,
        "status": status,
        "summary": summary,
        "detail": detail,
        "fixes": fixes or [],
        "data": data or {},
    }


def summarize_overall(checks):
    statuses = [check["status"] for check in checks]
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "ok"


def release_fix_suggestions(error, skill_name, branch=None):
    fixes = []
    if "worktree is dirty" in error:
        fixes.append(
            "Commit or stash local changes, then rerun `python3 scripts/doctor-signing.py "
            + skill_name
            + "`"
        )
    elif "has no upstream" in error:
        current_branch = branch or "main"
        fixes.append(f"Set an upstream with `git push -u origin {current_branch}`")
    elif "ahead of" in error:
        fixes.append(
            "Push the current branch so release checks and the release tag point at the same commit"
        )
    elif "behind" in error:
        fixes.append("Fast-forward from upstream before tagging, for example `git pull --ff-only`")
    elif "publisher" in error or "namespace transfer" in error:
        fixes.append("Update `policy/namespace-policy.json`, then rerun `scripts/check-all.sh`")
    elif "expected release tag is missing" in error:
        fixes.append(
            "Create and push the release tag with "
            f"`scripts/release-skill.sh {skill_name} --push-tag`"
        )
    elif "not pushed to" in error:
        fixes.append(
            f"Push the release tag with `scripts/release-skill.sh {skill_name} --push-tag` "
            "or `git push origin refs/tags/...`"
        )
    elif "did not verify against repo-managed signers" in error:
        fixes.append(
            "Ensure the configured SSH signing key is committed in `config/allowed_signers` "
            "and matches the release tag signer"
        )
    return fixes


def render_signing_doctor_report(report) -> str:
    lines = [
        "doctor: signing bootstrap and release readiness",
        f"overall: {report['overall_status'].upper()}",
    ]
    for check in report["checks"]:
        lines.append("")
        lines.append(f"[{check['status'].upper()}] {check['id']}: {check['summary']}")
        if check.get("detail"):
            lines.append(f"  detail: {check['detail']}")
        for fix in check.get("fixes") or []:
            lines.append(f"  fix: {fix}")
    return "\n".join(lines)


def git_config_value(root: Path, key: str) -> str:
    result = subprocess.run(
        ["git", "config", "--get", key],
        cwd=root,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


# ── Individual diagnostic checks ──────────────────────────────────────────────


def _check_signing_config(root: Path) -> tuple[dict | None, list[dict]]:
    """Load signing and attestation config. Returns (signing, checks)."""
    try:
        signing = load_signing_config(root)
        load_attestation_config(root)
        return signing, []
    except Exception as exc:
        return None, [
            make_check(
                "signing-config",
                "fail",
                "Cannot load signing configuration",
                detail=str(exc),
            )
        ]


def _check_allowed_signers(signing: dict, identity: str | None) -> tuple[list[dict], list[dict]]:
    """Parse and validate allowed signers. Returns (allowed_entries, checks)."""
    try:
        allowed_entries = parse_allowed_signers(signing["allowed_signers_path"])
    except SigningBootstrapError as exc:
        return [], [
            make_check(
                "allowed-signers-format",
                "fail",
                f"{signing['allowed_signers_rel']} is malformed",
                detail=str(exc),
                fixes=[
                    f"Fix the malformed line in `{signing['allowed_signers_rel']}` "
                    "and rerun `scripts/check-all.sh`"
                ],
            )
        ]

    if not allowed_entries:
        identity_hint = identity or "release-signer"
        return [], [
            make_check(
                "trusted-signers",
                "fail",
                f"{signing['allowed_signers_rel']} has no trusted signer entries",
                detail=(
                    "Stable tag verification and release attestation verification remain "
                    "blocked until at least one trusted public key is committed."
                ),
                fixes=[
                    "Generate or reuse a key, then run "
                    f"`uv run infinitas release bootstrap-signing add-allowed-signer "
                    f"--identity {identity_hint} --key ~/.ssh/id_ed25519`",
                    "Commit and push the updated `config/allowed_signers` before "
                    "creating the first stable tag",
                ],
            )
        ]

    return allowed_entries, [
        make_check(
            "trusted-signers",
            "ok",
            (
                f"{signing['allowed_signers_rel']} contains "
                f"{len(allowed_entries)} trusted signer entr"
                + ("y" if len(allowed_entries) == 1 else "ies")
            ),
            detail=(
                "Committed signer identities are available for tag and attestation verification."
            ),
            data={"identities": [entry["identity"] for entry in allowed_entries]},
        )
    ]


def _check_signing_key(
    signing: dict,
    allowed_entries: list[dict],
    identity: str | None,
    root: Path,
) -> tuple[list[str], list[dict]]:
    """Validate signing key configuration. Returns (inferred_identities, checks)."""
    configured_key = signing_key_path(root, signing)
    if not configured_key:
        identity_hint = identity or "release-signer"
        return [], [
            make_check(
                "signing-key",
                "fail",
                "No SSH signing key is configured for stable release tags",
                detail=(
                    f"Set `{signing['signing_key_env']}` or `git config user.signingkey` "
                    "to a private SSH key path."
                ),
                fixes=[
                    "Create a key with "
                    f"`uv run infinitas release bootstrap-signing init-key "
                    f"--identity {identity_hint} --output "
                    "~/.ssh/infinitas-skill-release-signing`",
                    "Point git at that key with "
                    "`uv run infinitas release bootstrap-signing configure-git "
                    "--key ~/.ssh/infinitas-skill-release-signing`",
                ],
            )
        ]

    key_path = Path(configured_key).expanduser()
    if not key_path.exists():
        return [], [
            make_check(
                "signing-key",
                "fail",
                f"Configured SSH signing key does not exist: {key_path}",
                detail=(
                    "Release tag creation cannot succeed until the configured "
                    "private key path is present."
                ),
                fixes=[
                    "Update the key path in git config or recreate the key with "
                    "`uv run infinitas release bootstrap-signing init-key ...`"
                ],
            )
        ]

    try:
        configured_public_key = public_key_from_key_path(key_path)
    except SigningBootstrapError as exc:
        return [], [
            make_check(
                "signing-key",
                "fail",
                "Cannot read configured SSH signing key",
                detail=str(exc),
            )
        ]

    inferred_identities = signer_identities_for_key(allowed_entries, configured_public_key)
    if allowed_entries and not inferred_identities:
        identity_hint = identity or "release-signer"
        return [], [
            make_check(
                "signing-key-trust",
                "fail",
                "Configured SSH signing key is not trusted by the repository",
                detail=(
                    f"The key at `{key_path}` is not present in `{signing['allowed_signers_rel']}`."
                ),
                fixes=[
                    "Run "
                    f"`uv run infinitas release bootstrap-signing "
                    f"add-allowed-signer --identity {identity_hint} "
                    f"--key {key_path}`",
                    f"Commit and push the updated `{signing['allowed_signers_rel']}` "
                    "before tagging",
                ],
            )
        ]

    detail = f"Configured key path: {key_path}"
    if inferred_identities:
        detail += "; matched identities: " + ", ".join(inferred_identities)
    return inferred_identities, [
        make_check(
            "signing-key",
            "ok",
            "An SSH signing key is configured for release tags",
            detail=detail,
        )
    ]


def _check_git_gpg_format(root: Path) -> list[dict]:
    """Check git gpg.format configuration."""
    gpg_format = git_config_value(root, "gpg.format")
    if gpg_format and gpg_format != "ssh":
        return [
            make_check(
                "git-gpg-format",
                "warn",
                f"git config gpg.format is {gpg_format!r}, not ssh",
                detail=(
                    "Release helpers override this automatically, but setting `ssh` "
                    "keeps manual git tag signing consistent."
                ),
                fixes=[
                    "Run `uv run infinitas release bootstrap-signing configure-git "
                    "--key <private-key>` to normalize local git config"
                ],
            )
        ]
    return [
        make_check(
            "git-gpg-format",
            "ok",
            "Git SSH signing format is configured or will be injected by release helpers",
            detail="Manual `git tag -s` use is simplest when `gpg.format=ssh`.",
        )
    ]


def _check_release_preflight(
    skill_state: dict,
    skill_name: str,
    has_provenance_artifact: bool,
    root: Path,
) -> tuple[Path | None, list[dict]]:
    """Check release preflight state. Returns (expected_provenance, checks)."""
    skill_meta = skill_state.get("skill") or {}
    expected_provenance = (
        Path(root)
        / "catalog"
        / "provenance"
        / f"{skill_meta.get('name')}-{skill_meta.get('version')}.json"
    )
    branch = ((skill_state.get("git") or {}).get("branch") or "").strip() or None
    preflight_errors = skill_state.get("errors") or []

    if not preflight_errors:
        return expected_provenance, [
            make_check(
                "release-preflight",
                "ok",
                f"Release preflight is clean for {skill_name}",
                detail=(
                    "Worktree, upstream sync, and namespace policy checks are "
                    "ready for signed tag creation."
                ),
            )
        ]

    dirty_only = (
        len(preflight_errors) == 1
        and "worktree is dirty" in preflight_errors[0]
        and has_provenance_artifact
    )
    fixes = []
    for error in preflight_errors:
        fixes.extend(release_fix_suggestions(error, skill_name, branch=branch))
    return expected_provenance, [
        make_check(
            "release-preflight",
            "warn" if dirty_only else "fail",
            (
                f"Release preflight for {skill_name} is dirty after writing release artifacts"
                if dirty_only
                else f"Release preflight is blocked for {skill_name}"
            ),
            detail=(
                "Current tag and attestation can verify, but you should "
                "commit or clean generated release artifacts before the "
                "next stable release."
                if dirty_only
                else "; ".join(preflight_errors)
            ),
            fixes=list(
                dict.fromkeys(
                    fixes
                    or [
                        "Commit generated provenance or clean the worktree "
                        "before the next stable release"
                    ]
                )
            ),
            data={"errors": preflight_errors},
        )
    ]


def _check_namespace_signer_policy(
    skill_state: dict,
    publisher: str | None,
    inferred_identities: list[str],
) -> list[dict]:
    """Check namespace signer authorization."""
    release = skill_state.get("release") or {}
    if not (publisher and inferred_identities and release.get("authorized_signers")):
        return []

    unauthorized = [
        actor for actor in inferred_identities if actor not in release.get("authorized_signers", [])
    ]
    if unauthorized:
        return [
            make_check(
                "namespace-signer-policy",
                "warn",
                f"Configured signer identities are not authorized for publisher {publisher}",
                detail="Current matches: " + ", ".join(unauthorized),
                fixes=[
                    "Authorize them with "
                    "`uv run infinitas release bootstrap-signing "
                    "authorize-publisher --publisher "
                    + publisher
                    + " "
                    + " ".join(f"--signer {actor}" for actor in unauthorized)
                    + "`"
                ],
            )
        ]
    return [
        make_check(
            "namespace-signer-policy",
            "ok",
            f"Configured signer identity is authorized for publisher {publisher}",
        )
    ]


def _check_namespace_releaser_policy(
    skill_state: dict,
    publisher: str | None,
    root: Path,
) -> list[dict]:
    """Check namespace releaser authorization."""
    release = skill_state.get("release") or {}
    releaser_identity = resolve_releaser_identity(root)
    authorized_releasers = release.get("authorized_releasers") or []

    if not (publisher and releaser_identity and authorized_releasers):
        return []

    if releaser_identity not in authorized_releasers:
        return [
            make_check(
                "namespace-releaser-policy",
                "warn",
                "Releaser identity "
                f"{releaser_identity!r} is not authorized for publisher {publisher}",
                detail=(
                    "Release output still works today, but audit warnings will "
                    "remain until policy is updated."
                ),
                fixes=[
                    "Run "
                    f"`uv run infinitas release bootstrap-signing "
                    f"authorize-publisher --publisher {publisher} "
                    f"--releaser {json.dumps(releaser_identity)}`"
                ],
            )
        ]
    return [
        make_check(
            "namespace-releaser-policy",
            "ok",
            f"Releaser identity {releaser_identity!r} is authorized for publisher {publisher}",
        )
    ]


def _check_release_tag(skill_state: dict, skill_name: str) -> list[dict]:
    """Check release tag state."""
    tag_state = (skill_state.get("git") or {}).get("local_tag") or {}
    expected_tag = skill_state["git"]["expected_tag"]

    if not tag_state.get("exists"):
        return [
            make_check(
                "release-tag",
                "info",
                f"No local signed release tag exists yet for {expected_tag}",
                detail="Tag signing is ready once the bootstrap checks above are green.",
                fixes=[
                    f"Create and push the first stable tag with "
                    f"`scripts/release-skill.sh {skill_name} --push-tag`"
                ],
            )
        ]

    if tag_state.get("verified"):
        remote_tag = (skill_state.get("git") or {}).get("remote_tag") or {}
        if remote_tag.get("tag_exists"):
            return [
                make_check(
                    "release-tag",
                    "ok",
                    f"Release tag {expected_tag} is signed and pushed",
                    detail="Repo-managed SSH signers verify the current stable tag.",
                )
            ]
        return [
            make_check(
                "release-tag",
                "info",
                f"Release tag {expected_tag} is signed locally but not pushed yet",
                fixes=[f"Push it with `scripts/release-skill.sh {skill_name} --push-tag`"],
            )
        ]

    detail = tag_state.get("verification_error") or "Tag exists but verification failed"
    return [
        make_check(
            "release-tag",
            "fail",
            f"Release tag {expected_tag} is present but not verified",
            detail=detail,
            fixes=[
                "Recreate it with "
                f"`scripts/release-skill-tag.sh {skill_name} --create --force` "
                "after fixing the signer bootstrap"
            ],
        )
    ]


def _check_attestation(
    provenance_path: Path | None,
    provenance_arg: str | None,
    identity: str | None,
    root: Path,
) -> list[dict]:
    """Check attestation verification."""
    if not provenance_path:
        return []

    if provenance_path.exists():
        try:
            verified = verify_attestation(str(provenance_path), identity=identity, root=root)
        except AttestationError as exc:
            return [
                make_check(
                    "attestation",
                    "fail",
                    f"Attestation verification failed for {provenance_path}",
                    detail=str(exc),
                    fixes=[
                        "Repair the signing bootstrap or regenerate provenance with "
                        "`scripts/release-skill.sh <skill> --write-provenance`"
                    ],
                )
            ]
        return [
            make_check(
                "attestation",
                "ok",
                f"Attestation verifies for {provenance_path.name}",
                detail=f"signer={verified['identity']} namespace={verified['namespace']}",
            )
        ]

    if provenance_arg:
        return [
            make_check(
                "attestation",
                "fail",
                f"Provenance file does not exist: {provenance_path}",
                detail=(
                    "Doctor cannot verify an attestation bundle until the JSON payload exists."
                ),
                fixes=["Create it with `scripts/release-skill.sh <skill> --write-provenance`"],
            )
        ]

    return [
        make_check(
            "attestation",
            "info",
            f"No attestation bundle exists yet at {provenance_path}",
            detail=(
                "Attestation verification will become available immediately "
                "after the first stable release writes provenance."
            ),
            fixes=[
                "Write it with "
                "`scripts/release-skill.sh <skill> --notes-out "
                "/tmp/<skill>-release.md --write-provenance`"
            ],
        )
    ]


# ── Main report builder ───────────────────────────────────────────────────────


def build_signing_doctor_report(
    *,
    skill: str | None = None,
    identity: str | None = None,
    provenance: str | None = None,
    root: Path = ROOT,
):
    checks = []
    skill_dir = None
    skill_state = None
    skill_name = skill or "<skill>"
    inferred_signer_identities = []
    expected_provenance = None

    # 1. Load signing config
    signing, config_checks = _check_signing_config(root)
    if config_checks:
        return {
            "overall_status": "fail",
            "skill": None,
            "expected_provenance": None,
            "inferred_signer_identities": [],
            "checks": config_checks,
        }
    signing = signing or {}

    # 2. Check allowed signers
    allowed_entries, signers_checks = _check_allowed_signers(signing, identity)
    checks.extend(signers_checks)

    # 3. Check signing key
    key_identities, key_checks = _check_signing_key(signing, allowed_entries, identity, root)
    inferred_signer_identities = key_identities
    checks.extend(key_checks)

    # 4. Check git gpg.format
    checks.extend(_check_git_gpg_format(root))

    # 5. Resolve skill and check release state
    if skill:
        try:
            skill_dir = resolve_skill(root, skill)
            skill_name = skill_dir.name
            skill_state = collect_release_state(skill_dir, mode="preflight", root=root)
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
            skill_meta = skill_state.get("skill") or {}
            publisher = skill_meta.get("publisher")

            # Determine provenance path
            has_provenance_artifact = False
            if provenance:
                has_provenance_artifact = Path(provenance).expanduser().resolve().exists()
            expected_provenance_candidate = (
                Path(root)
                / "catalog"
                / "provenance"
                / f"{skill_meta.get('name')}-{skill_meta.get('version')}.json"
            )
            if not provenance and expected_provenance_candidate.exists():
                has_provenance_artifact = True

            # 6. Check release preflight
            prov, preflight_checks = _check_release_preflight(
                skill_state, skill_name, has_provenance_artifact, root
            )
            if prov and expected_provenance is None:
                expected_provenance = prov
            checks.extend(preflight_checks)

            # 7. Check namespace signer policy
            checks.extend(
                _check_namespace_signer_policy(skill_state, publisher, inferred_signer_identities)
            )

            # 8. Check namespace releaser policy
            checks.extend(_check_namespace_releaser_policy(skill_state, publisher, root))

            # 9. Check release tag
            checks.extend(_check_release_tag(skill_state, skill_name))

    # 10. Check attestation
    provenance_path = Path(provenance).resolve() if provenance else expected_provenance
    checks.extend(_check_attestation(provenance_path, provenance, identity, root))

    return {
        "overall_status": summarize_overall(checks),
        "skill": str(skill_dir.relative_to(root)) if skill_dir else None,
        "expected_provenance": (
            str(provenance_path.relative_to(root))
            if provenance_path and provenance_path.is_relative_to(root)
            else (str(provenance_path) if provenance_path else None)
        ),
        "inferred_signer_identities": inferred_signer_identities,
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


__all__ = [
    "ROOT",
    "build_signing_doctor_report",
    "build_signing_doctor_parser",
    "configure_signing_doctor_parser",
    "git_config_value",
    "make_check",
    "parse_signing_doctor_args",
    "release_fix_suggestions",
    "render_signing_doctor_report",
    "signing_doctor_main",
    "summarize_overall",
]
