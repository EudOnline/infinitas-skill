#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: scripts/release-skill.sh <skill-name-or-path> [--preview] [--create-tag] [--sign-tag] [--unsigned-tag] [--push-tag] [--github-release] [--notes-out PATH] [--write-provenance] [--sign-provenance] [--ssh-sign-provenance] [--ssh-verify-provenance] [--ssh-key PATH] [--signer IDENTITY] [--releaser IDENTITY]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$1"
shift || true
PREVIEW=0
CREATE_TAG=0
UNSIGNED_TAG=0
PUSH_TAG=0
GITHUB_RELEASE=0
NOTES_OUT=""
WRITE_PROVENANCE=0
SIGN_PROVENANCE=0
SSH_SIGN_PROVENANCE=0
SSH_VERIFY_PROVENANCE=0
SSH_KEY=""
SIGNER=""
RELEASER=""
readarray -t ATT_CFG < <(python3 - <<'PY' "$ROOT"
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
config = json.loads((root / 'config' / 'signing.json').read_text(encoding='utf-8'))
att = config.get('attestation') or {}
policy = att.get('policy') or {}
mode = policy.get('mode', 'enforce')
print(att.get('signature_ext') or config.get('signature_ext') or '.ssig')
print('1' if policy.get('require_verified_attestation_for_release_output', mode == 'enforce') else '0')
print('1' if policy.get('require_verified_attestation_for_distribution', mode == 'enforce') else '0')
PY
)
ATT_SIGNATURE_EXT="${ATT_CFG[0]}"
ATT_REQUIRE_RELEASE="${ATT_CFG[1]}"
ATT_REQUIRE_DISTRIBUTION="${ATT_CFG[2]}"

resolve_skill() {
  local name="$1"
  if [[ -d "$name" && -f "$name/_meta.json" ]]; then
    printf '%s' "$name"
    return
  fi
  for stage in active incubating archived; do
    if [[ -d "$ROOT/skills/$stage/$name" ]]; then
      printf '%s' "$ROOT/skills/$stage/$name"
      return
    fi
  done
  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --preview)
      PREVIEW=1
      shift
      ;;
    --create-tag)
      CREATE_TAG=1
      shift
      ;;
    --sign-tag)
      CREATE_TAG=1
      shift
      ;;
    --unsigned-tag)
      CREATE_TAG=1
      UNSIGNED_TAG=1
      shift
      ;;
    --push-tag)
      PUSH_TAG=1
      CREATE_TAG=1
      shift
      ;;
    --github-release)
      GITHUB_RELEASE=1
      CREATE_TAG=1
      PUSH_TAG=1
      shift
      ;;
    --notes-out)
      NOTES_OUT="${2:-}"
      shift 2
      ;;
    --write-provenance)
      WRITE_PROVENANCE=1
      shift
      ;;
    --sign-provenance)
      SIGN_PROVENANCE=1
      WRITE_PROVENANCE=1
      shift
      ;;
    --ssh-sign-provenance)
      SSH_SIGN_PROVENANCE=1
      WRITE_PROVENANCE=1
      shift
      ;;
    --ssh-verify-provenance)
      SSH_VERIFY_PROVENANCE=1
      shift
      ;;
    --ssh-key)
      SSH_KEY="${2:-}"
      shift 2
      ;;
    --signer)
      SIGNER="${2:-}"
      shift 2
      ;;
    --releaser)
      RELEASER="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ $PREVIEW -eq 1 && ($CREATE_TAG -eq 1 || $PUSH_TAG -eq 1 || $GITHUB_RELEASE -eq 1 || $WRITE_PROVENANCE -eq 1 || $SSH_VERIFY_PROVENANCE -eq 1) ]]; then
  echo "--preview is read-only; do not combine it with tag creation, provenance, or publishing flags" >&2
  exit 1
fi

DIR="$(resolve_skill "$TARGET")" || { echo "cannot resolve skill: $TARGET" >&2; exit 1; }
"$ROOT/scripts/check-skill.sh" "$DIR" >/dev/null
"$ROOT/scripts/check-all.sh" >/dev/null

META_JSON="$(mktemp)"
python3 - "$DIR" "$META_JSON" <<'PY'
import json, re, sys
from pathlib import Path
skill_dir = Path(sys.argv[1])
out = Path(sys.argv[2])
meta = json.loads((skill_dir / '_meta.json').read_text(encoding='utf-8'))
name = meta['name']
version = meta['version']
status = meta.get('status')
changelog = (skill_dir / 'CHANGELOG.md').read_text(encoding='utf-8')
pattern = re.compile(rf'^##\s+{re.escape(version)}\s+-.*?(?=^##\s+|\Z)', re.M | re.S)
m = pattern.search(changelog)
notes = m.group(0).strip() if m else f'## {version}\n\n- No matching changelog section found.'
out.write_text(json.dumps({'name': name, 'version': version, 'status': status, 'notes': notes}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY

NAME="$(python3 - <<'PY' "$META_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['name'])
PY
)"
VERSION="$(python3 - <<'PY' "$META_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['version'])
PY
)"
STATUS="$(python3 - <<'PY' "$META_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['status'])
PY
)"
TAG="skill/$NAME/v$VERSION"

if [[ "$STATUS" != "active" ]]; then
  rm -f "$META_JSON"
  echo "release-skill.sh expects an active skill; current status is $STATUS" >&2
  exit 1
fi

if [[ $UNSIGNED_TAG -eq 1 && ($PUSH_TAG -eq 1 || $GITHUB_RELEASE -eq 1 || $WRITE_PROVENANCE -eq 1 || -n "$NOTES_OUT" ) ]]; then
  rm -f "$META_JSON"
  echo "stable release output requires a signed tag; --unsigned-tag is only for local non-release experiments" >&2
  exit 1
fi

if [[ $ATT_REQUIRE_RELEASE -eq 1 && -n "$NOTES_OUT" && $WRITE_PROVENANCE -eq 0 ]]; then
  rm -f "$META_JSON"
  echo "v9 attestation policy requires --write-provenance before writing release notes or other release artifacts" >&2
  exit 1
fi

if [[ $ATT_REQUIRE_DISTRIBUTION -eq 1 && $GITHUB_RELEASE -eq 1 && $WRITE_PROVENANCE -eq 0 ]]; then
  rm -f "$META_JSON"
  echo "v9 attestation policy requires --write-provenance before creating a GitHub release" >&2
  exit 1
fi

AUTO_VERIFY_ATTESTATION=0
if [[ $WRITE_PROVENANCE -eq 1 && ($ATT_REQUIRE_RELEASE -eq 1 || $ATT_REQUIRE_DISTRIBUTION -eq 1) ]]; then
  AUTO_VERIFY_ATTESTATION=1
  SSH_SIGN_PROVENANCE=1
  SSH_VERIFY_PROVENANCE=1
fi

print_raw_notes() {
  python3 - <<'PY' "$META_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['notes'])
PY
}

write_release_notes() {
  python3 - <<'PY' "$META_JSON" "$STATE_JSON" "$1"
import json, sys
meta = json.load(open(sys.argv[1], encoding='utf-8'))
state = json.load(open(sys.argv[2], encoding='utf-8'))
out_path = sys.argv[3]
remote = state['git']['remote_tag'].get('name') or 'origin'
commit = state['git']['remote_tag'].get('target_commit') or state['git']['local_tag'].get('target_commit') or state['git']['head_commit']
signer = state['git']['local_tag'].get('signer')
notes = meta['notes'].rstrip() + '\n\n## Source Snapshot\n\n'
notes += f"- Tag: `{state['git']['expected_tag']}`\n"
notes += f"- Ref: `refs/tags/{state['git']['expected_tag']}`\n"
notes += f"- Commit: `{commit}`\n"
notes += f"- Upstream: `{state['git']['upstream']}`\n"
notes += f"- Remote: `{remote}`\n"
if signer:
    notes += f"- Verified signer: `{signer}`\n"
if out_path == '-':
    print(notes)
else:
    open(out_path, 'w', encoding='utf-8').write(notes)
PY
}

FULL_RELEASE=0
if [[ $PREVIEW -eq 0 ]]; then
  if [[ $PUSH_TAG -eq 1 || $GITHUB_RELEASE -eq 1 || $WRITE_PROVENANCE -eq 1 || -n "$NOTES_OUT" ]]; then
    FULL_RELEASE=1
  elif [[ $CREATE_TAG -eq 0 ]]; then
    FULL_RELEASE=1
  fi
fi

if [[ $PREVIEW -eq 1 ]]; then
  echo "skill: $NAME"
  echo "version: $VERSION"
  echo "status: $STATUS"
  echo "tag: $TAG"
  echo
  print_raw_notes
  if [[ -n "$NOTES_OUT" ]]; then
    print_raw_notes > "$NOTES_OUT"
    echo "wrote preview notes: $NOTES_OUT"
  fi
  rm -f "$META_JSON"
  exit 0
fi

if [[ $CREATE_TAG -eq 1 || $PUSH_TAG -eq 1 ]]; then
  TAG_ARGS=("$DIR")
  [[ $CREATE_TAG -eq 1 ]] && TAG_ARGS+=(--create)
  [[ $PUSH_TAG -eq 1 ]] && TAG_ARGS+=(--push)
  [[ $UNSIGNED_TAG -eq 1 ]] && TAG_ARGS+=(--unsigned)
  "$ROOT/scripts/release-skill-tag.sh" "${TAG_ARGS[@]}"
fi

STATE_JSON="$(mktemp)"
if [[ $FULL_RELEASE -eq 1 ]]; then
  if ! python3 "$ROOT/scripts/check-release-state.py" "$DIR" --json > "$STATE_JSON"; then
    python3 "$ROOT/scripts/check-release-state.py" "$DIR" || true
    rm -f "$META_JSON" "$STATE_JSON"
    exit 1
  fi
  REMOTE_NAME="$(python3 - <<'PY' "$STATE_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['git']['remote_tag'].get('name') or 'origin')
PY
)"
  RELEASE_COMMIT="$(python3 - <<'PY' "$STATE_JSON"
import json, sys
state = json.load(open(sys.argv[1], encoding='utf-8'))
print(state['git']['remote_tag'].get('target_commit') or state['git']['local_tag'].get('target_commit') or state['git']['head_commit'])
PY
)"
  SIGNER_NAME="$(python3 - <<'PY' "$STATE_JSON"
import json, sys
print(json.load(open(sys.argv[1], encoding='utf-8'))['git']['local_tag'].get('signer') or '')
PY
)"
  RELEASER_NAME="$(python3 - <<'PY' "$STATE_JSON"
import json, sys
print((json.load(open(sys.argv[1], encoding='utf-8')).get('release') or {}).get('releaser_identity') or '')
PY
  )"
  ATTESTATION_KEY="$(python3 - <<'PY' "$STATE_JSON"
import json, sys
state = json.load(open(sys.argv[1], encoding='utf-8'))
print((state.get('signing') or {}).get('signing_key') or '')
PY
)"
  echo "skill: $NAME"
  echo "version: $VERSION"
  echo "status: $STATUS"
  echo "tag: $TAG"
  echo "release_ref: refs/tags/$TAG"
  echo "commit: $RELEASE_COMMIT"
  echo "remote: $REMOTE_NAME"
  if [[ -n "$SIGNER_NAME" ]]; then
    echo "verified_signer: $SIGNER_NAME"
  fi
  if [[ -n "$RELEASER_NAME" ]]; then
    echo "releaser: $RELEASER_NAME"
  fi
  echo
  write_release_notes -
fi

if [[ -n "$NOTES_OUT" ]]; then
  write_release_notes "$NOTES_OUT"
  echo "wrote notes: $NOTES_OUT"
fi

if [[ $WRITE_PROVENANCE -eq 1 ]]; then
  mkdir -p "$ROOT/catalog/provenance"
  PROV="$ROOT/catalog/provenance/$NAME-$VERSION.json"
  TMP_PROV="$(mktemp)"
  EFFECTIVE_SIGNER="$SIGNER"
  [[ -n "$EFFECTIVE_SIGNER" ]] || EFFECTIVE_SIGNER="$SIGNER_NAME"
  EFFECTIVE_RELEASER="$RELEASER"
  [[ -n "$EFFECTIVE_RELEASER" ]] || EFFECTIVE_RELEASER="$RELEASER_NAME"
  EFFECTIVE_SSH_KEY="$SSH_KEY"
  [[ -n "$EFFECTIVE_SSH_KEY" ]] || EFFECTIVE_SSH_KEY="$ATTESTATION_KEY"
  GENERATE_ARGS=(python3 "$ROOT/scripts/generate-provenance.py" "$DIR" --output-name "$(basename "$PROV")")
  if [[ -n "$EFFECTIVE_SIGNER" ]]; then
    GENERATE_ARGS+=(--signer "$EFFECTIVE_SIGNER")
  fi
  if [[ -n "$EFFECTIVE_RELEASER" ]]; then
    GENERATE_ARGS+=(--releaser "$EFFECTIVE_RELEASER")
  fi
  "${GENERATE_ARGS[@]}" > "$TMP_PROV"
  TMP_SSH_SIG="$TMP_PROV$ATT_SIGNATURE_EXT"
  PROV_SSH_SIG="$PROV$ATT_SIGNATURE_EXT"
  if [[ $SSH_SIGN_PROVENANCE -eq 1 ]]; then
    [[ -n "$EFFECTIVE_SIGNER" ]] || { echo "cannot determine attestation signer identity; pass --signer or create a verified repo-managed signed tag first" >&2; rm -f "$TMP_PROV"; exit 1; }
    [[ -n "$EFFECTIVE_SSH_KEY" ]] || { echo "missing SSH attestation signing key; pass --ssh-key or configure the repo signing key before writing provenance" >&2; rm -f "$TMP_PROV"; exit 1; }
    "$ROOT/scripts/sign-provenance-ssh.sh" "$TMP_PROV" --key "$EFFECTIVE_SSH_KEY" >/dev/null
  fi
  mv "$TMP_PROV" "$PROV"
  if [[ -f "$TMP_SSH_SIG" ]]; then
    mv "$TMP_SSH_SIG" "$PROV_SSH_SIG"
  fi
  echo "wrote provenance: $PROV"
  if [[ $SIGN_PROVENANCE -eq 1 ]]; then
    python3 "$ROOT/scripts/sign-provenance.py" "$PROV" >/dev/null
    python3 "$ROOT/scripts/verify-provenance.py" "$PROV" >/dev/null
    echo "signed provenance: $PROV.sig.json"
  fi
  if [[ $SSH_SIGN_PROVENANCE -eq 1 ]]; then
    echo "ssh-signed provenance: $PROV_SSH_SIG"
  fi
  if [[ $SSH_VERIFY_PROVENANCE -eq 1 ]]; then
    VERIFY_ARGS=("$ROOT/scripts/verify-provenance-ssh.sh" "$PROV")
    [[ -n "$EFFECTIVE_SIGNER" ]] && VERIFY_ARGS+=(--identity "$EFFECTIVE_SIGNER")
    "${VERIFY_ARGS[@]}" >/dev/null
    if [[ $AUTO_VERIFY_ATTESTATION -eq 1 ]]; then
      echo "verified attestation: $PROV_SSH_SIG"
    else
      echo "ssh-verified provenance: $PROV_SSH_SIG"
    fi
  fi
fi

if [[ $GITHUB_RELEASE -eq 1 ]]; then
  TMP_NOTES="$(mktemp)"
  write_release_notes "$TMP_NOTES"
  gh release create "$TAG" --title "$TAG" --notes-file "$TMP_NOTES"
  rm -f "$TMP_NOTES"
fi

rm -f "$META_JSON" "$STATE_JSON"
