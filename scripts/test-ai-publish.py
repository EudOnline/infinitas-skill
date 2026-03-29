#!/usr/bin/env python3
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
AI_INDEX_PATH = ROOT / "catalog" / "ai-index.json"
EXPECTED_SKILLS = {
    "lvxiaoer/operate-infinitas-skill",
    "lvxiaoer/release-infinitas-skill",
    "lvxiaoer/consume-infinitas-skill",
    "lvxiaoer/federation-registry-ops",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path):
    if not path.exists():
        fail(f"missing JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")


def main() -> None:
    payload = load_json(AI_INDEX_PATH)
    install_policy = payload.get("install_policy") or {}
    if install_policy.get("mode") != "immutable-only":
        fail(f"expected immutable-only install policy, got {install_policy.get('mode')!r}")

    entries = {
        item.get("qualified_name"): item
        for item in payload.get("skills") or []
        if isinstance(item, dict) and item.get("qualified_name")
    }
    missing_skills = EXPECTED_SKILLS - set(entries)
    if missing_skills:
        fail(f"missing published AI index entries: {sorted(missing_skills)!r}")

    for qualified_name in sorted(EXPECTED_SKILLS):
        entry = entries[qualified_name]
        latest_version = entry.get("latest_version")
        if not isinstance(latest_version, str) or not latest_version.strip():
            fail(f"{qualified_name} is missing latest_version")
        versions = entry.get("versions") or {}
        version_entry = versions.get(latest_version)
        if not isinstance(version_entry, dict):
            fail(f"{qualified_name} is missing version entry for {latest_version!r}")
        for field in ["manifest_path", "bundle_path", "attestation_path"]:
            rel_path = version_entry.get(field)
            if not isinstance(rel_path, str) or not rel_path.strip():
                fail(f"{qualified_name} is missing {field}")
            if not (ROOT / rel_path).exists():
                fail(f"{qualified_name} references missing {field}: {rel_path}")
        trust_state = version_entry.get("trust_state")
        if not isinstance(trust_state, str) or not trust_state.strip():
            fail(f"{qualified_name} is missing version trust_state")

    print("OK: ai publish compatibility checks passed")


if __name__ == "__main__":
    main()
