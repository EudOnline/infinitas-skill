"""Compatibility evidence helpers for package-native release checks."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from infinitas_skill.compatibility.contracts import load_platform_profile_contract

EVIDENCE_ROOT = Path("catalog") / "compatibility-evidence"
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+]([A-Za-z0-9_.-]+))?$")
PLATFORM_ALIASES = {
    "claude": "claude",
    "claude-code": "claude",
    "claude_code": "claude",
    "codex": "codex",
    "openclaw": "openclaw",
    "open-claw": "openclaw",
    "open_claw": "openclaw",
}
KNOWN_STATES = {
    "adapted",
    "native",
    "degraded",
    "unsupported",
    "blocked",
    "broken",
    "unknown",
}
CANONICAL_RUNTIME_PLATFORM = "openclaw"


def compatibility_evidence_root(root: Path) -> Path:
    return Path(root).resolve() / EVIDENCE_ROOT


def normalize_platform_name(value):
    if not isinstance(value, str):
        return None
    token = value.strip().lower()
    if not token:
        return None
    return PLATFORM_ALIASES.get(token, token)


def normalize_declared_support(values):
    normalized = []
    for item in values or []:
        platform = normalize_platform_name(item)
        if platform and platform not in normalized:
            normalized.append(platform)
    return normalized


def _parse_iso8601(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be a non-empty string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_payload(payload):
    item = dict(payload or {})
    item["platform"] = normalize_platform_name(item.get("platform"))
    skill = item.get("skill") or item.get("name") or item.get("qualified_name")
    item["skill"] = skill.strip() if isinstance(skill, str) else skill
    if "qualified_name" in item and isinstance(item.get("qualified_name"), str):
        item["qualified_name"] = item["qualified_name"].strip()
    version = item.get("version")
    item["version"] = version.strip() if isinstance(version, str) else version
    state = item.get("state")
    item["state"] = state.strip().lower() if isinstance(state, str) else state
    checked_at = item.get("checked_at")
    item["checked_at"] = checked_at.strip() if isinstance(checked_at, str) else checked_at
    checker = item.get("checker")
    if isinstance(checker, str):
        item["checker"] = checker.strip()
    note = item.get("note")
    if isinstance(note, str):
        item["note"] = note.strip()
    return item


def validate_compatibility_evidence_payload(payload, *, path: Path | None = None):
    errors = []
    if not isinstance(payload, dict):
        return ["compatibility evidence payload must be an object"]

    item = _normalize_payload(payload)
    if not item.get("platform"):
        errors.append("platform must be a non-empty string")
    if not isinstance(item.get("skill"), str) or not item.get("skill"):
        errors.append("skill must be a non-empty string")
    version = item.get("version")
    if not isinstance(version, str) or not version:
        errors.append("version must be a non-empty string")
    elif not SEMVER_RE.match(version):
        errors.append(f"version must be semver, got {version!r}")
    state = item.get("state")
    if not isinstance(state, str) or not state:
        errors.append("state must be a non-empty string")
    elif state not in KNOWN_STATES:
        errors.append(f"state must be one of {sorted(KNOWN_STATES)!r}, got {state!r}")

    try:
        _parse_iso8601(item.get("checked_at"))
    except Exception:
        errors.append("checked_at must be a valid ISO-8601 timestamp")

    checker = item.get("checker")
    if checker is not None and (not isinstance(checker, str) or not checker):
        errors.append("checker must be a non-empty string when present")

    if path is not None:
        path = Path(path)
        if path.suffix != ".json":
            errors.append("evidence path must end with .json")
        else:
            version_from_path = path.stem
            if isinstance(version, str) and version and version_from_path != version:
                errors.append(
                    f"path version {version_from_path!r} does not match payload version {version!r}"
                )
            if len(path.parts) >= 3:
                skill_from_path = path.parts[-2]
                platform_from_path = normalize_platform_name(path.parts[-3])
                if isinstance(item.get("skill"), str) and item["skill"]:
                    skill_names = {item["skill"]}
                    qualified_name = item.get("qualified_name")
                    if isinstance(qualified_name, str) and qualified_name:
                        skill_names.add(qualified_name)
                        skill_names.add(qualified_name.split("/")[-1])
                    if skill_from_path not in skill_names:
                        errors.append(
                            f"path skill {skill_from_path!r} does not match payload skill "
                            f"{item['skill']!r}"
                        )
                if item.get("platform") and platform_from_path != item["platform"]:
                    errors.append(
                        f"path platform {platform_from_path!r} does not match payload "
                        f"platform {item['platform']!r}"
                    )

    return errors


def write_compatibility_evidence(path: Path, payload: dict) -> None:
    item = _normalize_payload(payload)
    errors = validate_compatibility_evidence_payload(item, path=path)
    if errors:
        raise ValueError("; ".join(errors))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_compatibility_evidence(root: Path) -> list[dict]:
    evidence_root = compatibility_evidence_root(root)
    if not evidence_root.exists():
        return []

    items = []
    for path in sorted(evidence_root.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_compatibility_evidence_payload(
            payload, path=path.relative_to(evidence_root)
        )
        if errors:
            raise ValueError(f"{path}: {'; '.join(errors)}")
        item = _normalize_payload(payload)
        item["evidence_path"] = str(path.relative_to(Path(root).resolve()))
        items.append(item)
    return items


def load_platform_contracts(root: Path) -> dict[str, dict]:
    root = Path(root).resolve()
    contracts = {}
    profiles_dir = root / "profiles"
    if not profiles_dir.exists():
        return contracts

    for path in sorted(profiles_dir.glob("*.json")):
        platform = normalize_platform_name(path.stem)
        if not platform:
            continue
        payload, errors = load_platform_profile_contract(path, platform)
        if errors:
            raise ValueError(f"{path}: {'; '.join(errors)}")
        contracts[platform] = {
            "last_verified": payload.get("last_verified"),
            "sources": payload.get("sources") or [],
        }
    return contracts


def _evidence_sort_key(item):
    checked_at = item.get("checked_at")
    try:
        parsed = _parse_iso8601(checked_at)
    except Exception:
        parsed = datetime.min
    return (parsed, item.get("evidence_path") or "")


def _skill_matches(item, evidence):
    if not isinstance(item, dict) or not isinstance(evidence, dict):
        return False
    version = item.get("version")
    if evidence.get("version") != version:
        return False

    qualified_name = item.get("qualified_name")
    if isinstance(evidence.get("qualified_name"), str) and evidence["qualified_name"]:
        return evidence["qualified_name"] == qualified_name

    names = set()
    if isinstance(item.get("name"), str) and item["name"]:
        names.add(item["name"])
    if isinstance(qualified_name, str) and qualified_name:
        names.add(qualified_name)
        names.add(qualified_name.split("/")[-1])
    return evidence.get("skill") in names


def _format_iso8601(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _freshness_payload(
    *,
    platform: str,
    verified_item: dict | None,
    contract: dict | None,
    policy: dict,
    now: datetime,
) -> dict:
    result = dict(verified_item or {})
    verified_policy = (policy.get("verified_support") or {}) if isinstance(policy, dict) else {}
    stale_after_days = verified_policy.get("stale_after_days", 30)
    contract_policy = verified_policy.get("contract_newer_than_evidence_policy", "stale")
    missing_policy = verified_policy.get("missing_policy", "unknown")

    contract_last_verified = (contract or {}).get("last_verified")
    if contract_last_verified:
        result["contract_last_verified"] = contract_last_verified

    checked_at = result.get("checked_at")
    checked_at_dt = None
    if isinstance(checked_at, str) and checked_at.strip():
        try:
            checked_at_dt = _parse_iso8601(checked_at)
        except Exception:
            checked_at_dt = None

    if checked_at_dt is not None:
        result["fresh_until"] = _format_iso8601(checked_at_dt + timedelta(days=stale_after_days))
        if now > checked_at_dt + timedelta(days=stale_after_days):
            result["freshness_state"] = "stale"
            result["freshness_reason"] = "age-expired"
            return result
        if contract_policy == "stale" and contract_last_verified:
            contract_date = datetime.fromisoformat(contract_last_verified).date()
            if contract_date > checked_at_dt.date():
                result["freshness_state"] = "stale"
                result["freshness_reason"] = "contract-newer-than-evidence"
                return result
        result["freshness_state"] = "fresh"
        result["freshness_reason"] = "not-applicable"
        return result

    result["freshness_state"] = missing_policy
    result["freshness_reason"] = "missing-evidence"
    return result


def merge_declared_and_verified_support(
    skill_entry: dict,
    evidence: list[dict],
    *,
    platform_contracts: dict | None = None,
    compatibility_policy: dict | None = None,
    now: datetime | None = None,
) -> dict:
    merged = dict(skill_entry or {})
    declared = normalize_declared_support(
        merged.get("declared_support") or merged.get("agent_compatible") or []
    )
    matched = [item for item in evidence or [] if _skill_matches(merged, item)]
    platform_contracts = platform_contracts or {}
    compatibility_policy = compatibility_policy or {
        "verified_support": {
            "stale_after_days": 30,
            "contract_newer_than_evidence_policy": "stale",
            "missing_policy": "unknown",
        }
    }
    now = now or datetime.now(timezone.utc)

    verified = {}
    for item in sorted(matched, key=_evidence_sort_key):
        platform = normalize_platform_name(item.get("platform"))
        if not platform:
            continue
        verified[platform] = {
            "state": item.get("state"),
            "checked_at": item.get("checked_at"),
            "checker": item.get("checker"),
            "evidence_path": item.get("evidence_path"),
        }
        note = item.get("note")
        if isinstance(note, str) and note:
            verified[platform]["note"] = note

    platforms = []
    for platform in declared + sorted(verified):
        if platform not in platforms:
            platforms.append(platform)
    for platform in platforms:
        verified.setdefault(platform, {"state": "unknown"})
        verified[platform] = _freshness_payload(
            platform=platform,
            verified_item=verified.get(platform),
            contract=platform_contracts.get(platform),
            policy=compatibility_policy,
            now=now,
        )

    merged["declared_support"] = declared
    merged["verified_support"] = verified
    return merged


def collect_canonical_runtime_support(
    skill_entry: dict,
    evidence: list[dict],
    *,
    platform_contracts: dict | None = None,
    compatibility_policy: dict | None = None,
    now: datetime | None = None,
    platform: str = CANONICAL_RUNTIME_PLATFORM,
) -> dict:
    platform = normalize_platform_name(platform) or CANONICAL_RUNTIME_PLATFORM
    platform_contracts = platform_contracts or {}
    compatibility_policy = compatibility_policy or {
        "verified_support": {
            "stale_after_days": 30,
            "contract_newer_than_evidence_policy": "stale",
            "missing_policy": "unknown",
        }
    }
    now = now or datetime.now(timezone.utc)

    matched = [
        item
        for item in evidence or []
        if _skill_matches(skill_entry, item)
        and normalize_platform_name(item.get("platform")) == platform
    ]

    verified_item = None
    if matched:
        latest = sorted(matched, key=_evidence_sort_key)[-1]
        verified_item = {
            "state": latest.get("state"),
            "checked_at": latest.get("checked_at"),
            "checker": latest.get("checker"),
            "evidence_path": latest.get("evidence_path"),
        }
        note = latest.get("note")
        if isinstance(note, str) and note:
            verified_item["note"] = note

    result = _freshness_payload(
        platform=platform,
        verified_item=verified_item or {"state": "unknown"},
        contract=platform_contracts.get(platform),
        policy=compatibility_policy,
        now=now,
    )
    result["platform"] = platform
    result["declared"] = platform in normalize_declared_support(
        skill_entry.get("declared_support") or skill_entry.get("agent_compatible") or []
    )
    return result
