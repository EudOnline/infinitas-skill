"""Skill identity and namespace policy helpers for package-native flows."""

from __future__ import annotations

import json
import re
from pathlib import Path

from infinitas_skill.root import ROOT

from .policy_pack import PolicyPackError, load_effective_policy_domain
from .team_policy import TeamPolicyError, expand_team_refs, load_team_policy

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PUBLISHER_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
QUALIFIED_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*$")


class NamespacePolicyError(Exception):
    def __init__(self, errors):
        super().__init__("invalid namespace policy")
        self.errors = errors


def unique_strings(values):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_actor_list(values):
    if values is None:
        return []
    if not isinstance(values, list):
        return []
    return unique_strings(
        [item.strip() for item in values if isinstance(item, str) and item.strip()]
    )


def normalize_team_list(values):
    if values is None:
        return []
    if not isinstance(values, list):
        return []
    return unique_strings(
        [item.strip() for item in values if isinstance(item, str) and item.strip()]
    )


def parse_requested_skill(value):
    text = (value or "").strip()
    if not text:
        return None, None
    if "/" not in text:
        return None, text
    publisher, name = text.split("/", 1)
    publisher = publisher.strip() or None
    name = name.strip() or None
    return publisher, name


def derive_qualified_name(name, publisher=None):
    if not isinstance(name, str) or not name.strip():
        return None
    skill_name = name.strip()
    if publisher:
        return f"{publisher}/{skill_name}"
    return skill_name


def display_name(payload):
    if not isinstance(payload, dict):
        return None
    return (
        payload.get("qualified_name")
        or derive_qualified_name(payload.get("name"), payload.get("publisher"))
        or payload.get("name")
    )


def normalize_skill_identity(meta):
    meta = meta if isinstance(meta, dict) else {}
    raw_name = meta.get("name")
    name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else None
    raw_publisher = meta.get("publisher")
    publisher = (
        raw_publisher.strip() if isinstance(raw_publisher, str) and raw_publisher.strip() else None
    )
    raw_owner = meta.get("owner")
    owner = raw_owner.strip() if isinstance(raw_owner, str) and raw_owner.strip() else None
    owners = normalize_actor_list(meta.get("owners"))
    if not owners and owner:
        owners = [owner]
    maintainers = normalize_actor_list(meta.get("maintainers"))
    raw_author = meta.get("author")
    author = raw_author.strip() if isinstance(raw_author, str) and raw_author.strip() else None
    if not author:
        author = owners[0] if owners else owner
    raw_qualified = meta.get("qualified_name")
    qualified_name = (
        raw_qualified.strip() if isinstance(raw_qualified, str) and raw_qualified.strip() else None
    )
    if not qualified_name:
        qualified_name = derive_qualified_name(name, publisher)
    return {
        "name": name,
        "publisher": publisher,
        "qualified_name": qualified_name,
        "identity_mode": "qualified" if publisher else "legacy",
        "owner": owner,
        "owners": owners,
        "maintainers": maintainers,
        "author": author,
    }


def validate_identity_metadata(meta):
    identity = normalize_skill_identity(meta)
    errors = []

    name = identity.get("name")
    publisher = identity.get("publisher")
    qualified_name = meta.get("qualified_name")
    owners_value = meta.get("owners")
    author_value = meta.get("author")

    if publisher is not None:
        if not isinstance(meta.get("publisher"), str) or not PUBLISHER_RE.match(publisher):
            errors.append(f"invalid publisher {meta.get('publisher')!r}")
    if qualified_name is not None:
        if not isinstance(qualified_name, str) or not qualified_name.strip():
            errors.append("qualified_name must be a non-empty string when present")
        elif "/" in qualified_name and not QUALIFIED_NAME_RE.match(qualified_name):
            errors.append(f"invalid qualified_name {qualified_name!r}")
        expected = derive_qualified_name(name, publisher)
        if expected and qualified_name.strip() != expected:
            errors.append(f"qualified_name {qualified_name!r} must equal {expected!r}")
    if owners_value is not None:
        if not isinstance(owners_value, list) or not all(
            isinstance(item, str) and item.strip() for item in owners_value
        ):
            errors.append("owners must be an array of non-empty strings when present")
    if author_value is not None and (not isinstance(author_value, str) or not author_value.strip()):
        errors.append("author must be a non-empty string when present")
    if (
        identity.get("owner")
        and identity.get("owners")
        and identity["owner"] not in identity["owners"]
    ):
        errors.append(f"owner {identity['owner']!r} must also appear in owners")

    return identity, errors


def load_namespace_policy(root=ROOT):
    path = Path(root).resolve() / "policy" / "namespace-policy.json"
    try:
        payload = load_effective_policy_domain(root, "namespace_policy")
    except PolicyPackError as exc:
        raise NamespacePolicyError(exc.errors) from exc
    try:
        team_policy = load_team_policy(root)
    except TeamPolicyError as exc:
        raise NamespacePolicyError(exc.errors) from exc

    errors = []
    unknown_root = sorted(
        set(payload) - {"$schema", "version", "compatibility", "publishers", "transfers"}
    )
    if unknown_root:
        errors.append(f"namespace-policy has unsupported keys: {', '.join(unknown_root)}")
    if "$schema" in payload and not isinstance(payload.get("$schema"), str):
        errors.append("namespace-policy $schema must be a string when present")
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        errors.append("namespace-policy version must be an integer >= 1")
    compatibility = payload.get("compatibility", {})
    if compatibility is None:
        compatibility = {}
    if not isinstance(compatibility, dict):
        errors.append("namespace-policy compatibility must be an object")
        compatibility = {}
    allow_unqualified = compatibility.get("allow_unqualified_names", True)
    if not isinstance(allow_unqualified, bool):
        errors.append("namespace-policy compatibility.allow_unqualified_names must be boolean")
        allow_unqualified = True

    publishers = {}
    raw_publishers = payload.get("publishers", {})
    if not isinstance(raw_publishers, dict):
        errors.append("namespace-policy publishers must be an object")
        raw_publishers = {}
    for name, raw_entry in raw_publishers.items():
        if not isinstance(name, str) or not PUBLISHER_RE.match(name):
            errors.append(f"namespace-policy publishers contains invalid publisher name {name!r}")
            continue
        if not isinstance(raw_entry, dict):
            errors.append(f"namespace-policy publishers.{name} must be an object")
            continue
        unknown = sorted(
            set(raw_entry)
            - {
                "owners",
                "owner_teams",
                "maintainers",
                "maintainer_teams",
                "authorized_signers",
                "authorized_signer_teams",
                "authorized_releasers",
                "authorized_releaser_teams",
            }
        )
        if unknown:
            errors.append(
                f"namespace-policy publishers.{name} has unsupported keys: {', '.join(unknown)}"
            )
        for field_name in [
            "owners",
            "maintainers",
            "authorized_signers",
            "authorized_releasers",
        ]:
            value = raw_entry.get(field_name)
            if value is not None and not isinstance(value, list):
                errors.append(
                    f"namespace-policy publishers.{name}.{field_name} must be an array when present"
                )
        for field_name in [
            "owner_teams",
            "maintainer_teams",
            "authorized_signer_teams",
            "authorized_releaser_teams",
        ]:
            value = raw_entry.get(field_name)
            if value is not None and not isinstance(value, list):
                errors.append(
                    f"namespace-policy publishers.{name}.{field_name} must be an array when present"
                )
        owners = normalize_actor_list(raw_entry.get("owners"))
        owner_teams = normalize_team_list(raw_entry.get("owner_teams"))
        maintainers = normalize_actor_list(raw_entry.get("maintainers"))
        maintainer_teams = normalize_team_list(raw_entry.get("maintainer_teams"))
        authorized_signer_teams = normalize_team_list(raw_entry.get("authorized_signer_teams"))
        authorized_releaser_teams = normalize_team_list(raw_entry.get("authorized_releaser_teams"))

        resolved_owner_teams = expand_team_refs(owner_teams, team_policy)
        resolved_maintainer_teams = expand_team_refs(maintainer_teams, team_policy)
        resolved_signer_teams = expand_team_refs(authorized_signer_teams, team_policy)
        resolved_releaser_teams = expand_team_refs(authorized_releaser_teams, team_policy)
        for field_name, report in [
            ("owner_teams", resolved_owner_teams),
            ("maintainer_teams", resolved_maintainer_teams),
            ("authorized_signer_teams", resolved_signer_teams),
            ("authorized_releaser_teams", resolved_releaser_teams),
        ]:
            for missing_team in report.get("missing_teams", []):
                errors.append(
                    "namespace-policy publishers."
                    f"{name}.{field_name} references unknown team {missing_team!r}"
                )

        resolved_owners = unique_strings(owners + resolved_owner_teams.get("actors", []))
        resolved_maintainers = unique_strings(
            resolved_owners + maintainers + resolved_maintainer_teams.get("actors", [])
        )
        authorized_signers = normalize_actor_list(
            raw_entry.get("authorized_signers")
        ) or unique_strings(resolved_maintainers + resolved_signer_teams.get("actors", []))
        authorized_releasers = normalize_actor_list(
            raw_entry.get("authorized_releasers")
        ) or unique_strings(resolved_maintainers + resolved_releaser_teams.get("actors", []))
        if not owners and not owner_teams:
            errors.append(
                "namespace-policy publishers."
                f"{name} must include at least one owner actor or owner team"
            )
        publishers[name] = {
            "owners": owners,
            "owner_teams": owner_teams,
            "maintainers": maintainers,
            "maintainer_teams": maintainer_teams,
            "authorized_signers": authorized_signers,
            "authorized_signer_teams": authorized_signer_teams,
            "authorized_releasers": authorized_releasers,
            "authorized_releaser_teams": authorized_releaser_teams,
            "resolved_owners": resolved_owners,
            "resolved_maintainers": resolved_maintainers,
        }

    transfers = []
    raw_transfers = payload.get("transfers", [])
    if raw_transfers is None:
        raw_transfers = []
    if not isinstance(raw_transfers, list):
        errors.append("namespace-policy transfers must be an array")
        raw_transfers = []
    for index, raw_entry in enumerate(raw_transfers, start=1):
        if not isinstance(raw_entry, dict):
            errors.append(f"namespace-policy transfers[{index}] must be an object")
            continue
        unknown = sorted(set(raw_entry) - {"name", "from", "to", "approved_by", "note"})
        if unknown:
            errors.append(
                f"namespace-policy transfers[{index}] has unsupported keys: {', '.join(unknown)}"
            )
        name = raw_entry.get("name")
        from_publisher = raw_entry.get("from")
        to_publisher = raw_entry.get("to")
        approved_by = normalize_actor_list(raw_entry.get("approved_by"))
        note = raw_entry.get("note")
        if not isinstance(name, str) or not SKILL_NAME_RE.match(name):
            errors.append(
                f"namespace-policy transfers[{index}].name must be a lowercase skill slug"
            )
            continue
        if from_publisher is not None and (
            not isinstance(from_publisher, str) or not PUBLISHER_RE.match(from_publisher)
        ):
            errors.append(
                f"namespace-policy transfers[{index}].from must be null or a publisher slug"
            )
            continue
        if to_publisher is not None and (
            not isinstance(to_publisher, str) or not PUBLISHER_RE.match(to_publisher)
        ):
            errors.append(
                f"namespace-policy transfers[{index}].to must be null or a publisher slug"
            )
            continue
        if not approved_by:
            errors.append(
                f"namespace-policy transfers[{index}].approved_by must include at least one actor"
            )
            continue
        if note is not None and (not isinstance(note, str) or not note.strip()):
            errors.append(
                f"namespace-policy transfers[{index}].note must be a non-empty string when present"
            )
            continue
        transfers.append(
            {
                "name": name,
                "from": from_publisher,
                "to": to_publisher,
                "approved_by": approved_by,
                "note": note.strip() if isinstance(note, str) and note.strip() else None,
            }
        )

    if errors:
        raise NamespacePolicyError(errors)

    return {
        "path": path,
        "version": version,
        "compatibility": {
            "allow_unqualified_names": allow_unqualified,
        },
        "team_policy": team_policy,
        "publishers": publishers,
        "transfers": transfers,
    }


def iter_registry_skill_dirs(root=ROOT):
    base_root = Path(root).resolve() / "skills"
    for stage in ["incubating", "active", "archived"]:
        stage_dir = base_root / stage
        if not stage_dir.exists():
            continue
        for child in sorted(
            path for path in stage_dir.iterdir() if path.is_dir() and (path / "_meta.json").exists()
        ):
            yield child.resolve()


def transfer_is_authorized(policy, name, from_publisher, to_publisher):
    for entry in policy.get("transfers", []):
        if entry.get("name") != name:
            continue
        if entry.get("from") != from_publisher:
            continue
        if entry.get("to") != to_publisher:
            continue
        return entry
    return None


def namespace_policy_report(skill_dir, root=ROOT, policy=None):
    root = Path(root).resolve()
    skill_dir = Path(skill_dir).resolve()
    policy = policy or load_namespace_policy(root)
    meta = json.loads((skill_dir / "_meta.json").read_text(encoding="utf-8"))
    identity, identity_errors = validate_identity_metadata(meta)

    errors = list(identity_errors)
    warnings = []
    publisher_entry = (
        policy["publishers"].get(identity.get("publisher")) if identity.get("publisher") else None
    )

    if identity.get("publisher"):
        if publisher_entry is None:
            errors.append(
                f"{skill_dir}: publisher {identity['publisher']!r} is not declared in "
                "policy/namespace-policy.json"
            )
        else:
            missing_owners = [
                item
                for item in identity.get("owners", [])
                if item not in publisher_entry.get("resolved_owners", [])
            ]
            if missing_owners:
                errors.append(
                    f"{skill_dir}: owners {', '.join(missing_owners)} are not authorized "
                    f"owners for publisher {identity['publisher']!r}"
                )
            allowed_maintainers = set(publisher_entry.get("resolved_owners", [])) | set(
                publisher_entry.get("resolved_maintainers", [])
            )
            missing_maintainers = [
                item for item in identity.get("maintainers", []) if item not in allowed_maintainers
            ]
            if missing_maintainers:
                errors.append(
                    f"{skill_dir}: maintainers {', '.join(missing_maintainers)} are not "
                    f"authorized for publisher {identity['publisher']!r}"
                )
    elif not policy["compatibility"].get("allow_unqualified_names", True):
        errors.append(
            f"{skill_dir}: unqualified legacy skill names are disabled by "
            "policy/namespace-policy.json"
        )

    transfer_required = False
    transfer_authorized = True
    transfer_matches = []
    competing_claims = []
    for other_dir in iter_registry_skill_dirs(root):
        if other_dir == skill_dir:
            continue
        try:
            other_meta = json.loads((other_dir / "_meta.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        other = normalize_skill_identity(other_meta)
        if not other.get("name"):
            continue
        same_name = other.get("name") == identity.get("name")
        same_qualified = bool(
            identity.get("qualified_name")
            and other.get("qualified_name") == identity.get("qualified_name")
        )
        publisher_changed = other.get("publisher") != identity.get("publisher")
        if not publisher_changed or not (same_name or same_qualified):
            continue
        transfer_required = True
        competing_claims.append(
            {
                "path": str(other_dir.relative_to(root)),
                "stage": other_dir.parent.name,
                "publisher": other.get("publisher"),
                "qualified_name": other.get("qualified_name"),
                "name": other.get("name"),
            }
        )
        match = transfer_is_authorized(
            policy, identity.get("name"), other.get("publisher"), identity.get("publisher")
        )
        if not match and ("archived" in {skill_dir.parent.name, other_dir.parent.name}):
            match = transfer_is_authorized(
                policy, identity.get("name"), identity.get("publisher"), other.get("publisher")
            )
        if match:
            transfer_matches.append(match)
            continue
        transfer_authorized = False
        errors.append(
            f"{skill_dir}: namespace transfer for {identity.get('name')!r} from "
            f"{other.get('publisher')!r} to {identity.get('publisher')!r} is not "
            "authorized by policy/namespace-policy.json"
        )

    if publisher_entry:
        authorized_signers = list(publisher_entry.get("authorized_signers", []))
        authorized_releasers = list(publisher_entry.get("authorized_releasers", []))
    else:
        authorized_signers = unique_strings(
            identity.get("owners", []) + identity.get("maintainers", [])
        )
        authorized_releasers = unique_strings(
            identity.get("owners", []) + identity.get("maintainers", [])
        )

    if not authorized_signers:
        warnings.append(
            f"{skill_dir}: no authorized_signers resolved for "
            f"{display_name(identity) or skill_dir.name}"
        )

    return {
        "identity": identity,
        "policy_path": str(policy["path"].relative_to(root)),
        "policy_version": policy.get("version"),
        "authorized": not errors,
        "errors": errors,
        "warnings": warnings,
        "transfer_required": transfer_required,
        "transfer_authorized": transfer_authorized,
        "transfer_matches": transfer_matches,
        "competing_claims": competing_claims,
        "delegated_teams": {
            "owner_teams": list((publisher_entry or {}).get("owner_teams", [])),
            "maintainer_teams": list((publisher_entry or {}).get("maintainer_teams", [])),
            "authorized_signer_teams": list(
                (publisher_entry or {}).get("authorized_signer_teams", [])
            ),
            "authorized_releaser_teams": list(
                (publisher_entry or {}).get("authorized_releaser_teams", [])
            ),
        },
        "authorized_signers": authorized_signers,
        "authorized_releasers": authorized_releasers,
    }
