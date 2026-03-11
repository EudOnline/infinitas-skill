#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 scripts/check-registry-sources.py
python3 scripts/check-signing-config.py
python3 scripts/validate-registry.py
python3 scripts/test-namespace-identity.py
python3 scripts/check-registry-integrity.py
python3 scripts/check-promotion-policy.py
python3 scripts/test-review-governance.py
python3 scripts/test-compat-regression.py
if [[ "${INFINITAS_SKIP_RELEASE_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-release-invariants.py
fi
if [[ "${INFINITAS_SKIP_ATTESTATION_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-attestation-verification.py
fi
if [[ "${INFINITAS_SKIP_DISTRIBUTION_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-distribution-install.py
fi
if [[ "${INFINITAS_SKIP_AI_WRAPPER_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-ai-index.py
  python3 scripts/test-ai-pull.py
  python3 scripts/test-ai-publish.py
  python3 scripts/test-openclaw-import.py
  python3 scripts/test-openclaw-export.py
fi
if [[ "${INFINITAS_SKIP_BOOTSTRAP_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-signing-bootstrap.py
fi

while IFS= read -r dir; do
  [[ -n "$dir" ]] || continue
  scripts/check-skill.sh "$dir"
done < <(find skills -mindepth 2 -maxdepth 2 -type d -exec test -f '{}/_meta.json' ';' -print | sort)

before_catalog_norm="$(python3 - <<'PY'
import json
from pathlib import Path
for path in ['catalog/catalog.json','catalog/active.json','catalog/compatibility.json','catalog/registries.json','catalog/distributions.json','catalog/ai-index.json']:
    p = Path(path)
    if not p.exists():
        continue
    data = json.loads(p.read_text(encoding='utf-8'))
    data.pop('generated_at', None)
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))
PY
)"
scripts/build-catalog.sh >/dev/null
after_catalog_norm="$(python3 - <<'PY'
import json
from pathlib import Path
for path in ['catalog/catalog.json','catalog/active.json','catalog/compatibility.json','catalog/registries.json','catalog/distributions.json','catalog/ai-index.json']:
    p = Path(path)
    if not p.exists():
        continue
    data = json.loads(p.read_text(encoding='utf-8'))
    data.pop('generated_at', None)
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))
PY
)"

if [[ -n "$before_catalog_norm" && -n "$after_catalog_norm" && "$before_catalog_norm" != "$after_catalog_norm" ]]; then
  echo "FAIL: catalog contents changed; run scripts/build-catalog.sh and commit the result" >&2
  git --no-pager diff -- catalog/catalog.json catalog/active.json catalog/compatibility.json catalog/registries.json catalog/distributions.json catalog/ai-index.json || true
  exit 1
fi

echo "OK: full registry check passed"
