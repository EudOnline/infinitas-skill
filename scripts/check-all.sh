#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -x "$ROOT/.venv/bin/python3" ]]; then
  if ( ( set +e; "$ROOT/.venv/bin/python3" -c 'from alembic import command; import pytest' >/dev/null 2>&1 ) >/dev/null 2>&1 ); then
    export PATH="$ROOT/.venv/bin:$PATH"
  fi
fi

BLOCKS=("$@")
if [[ ${#BLOCKS[@]} -eq 0 ]]; then
  BLOCKS=(focused-integration hosted-ui full-regression)
fi
VALID_BLOCKS=(focused-integration hosted-ui full-regression)

validate_blocks() {
  local requested
  local valid
  for requested in "${BLOCKS[@]}"; do
    for valid in "${VALID_BLOCKS[@]}"; do
      if [[ "$requested" == "$valid" ]]; then
        continue 2
      fi
    done
    echo "FAIL: unknown check-all block '$requested' (expected one of: ${VALID_BLOCKS[*]})" >&2
    exit 1
  done
}

should_run() {
  local target="$1"
  local block
  for block in "${BLOCKS[@]}"; do
    if [[ "$block" == "$target" ]]; then
      return 0
    fi
  done
  return 1
}

validate_blocks

run_block() {
  echo "== $1 =="
}

if should_run focused-integration; then
  run_block focused-integration
  python3 -m pytest \
    tests/integration/test_cli_release_state.py \
    tests/integration/test_cli_server_ops.py \
    tests/integration/test_private_registry_ui.py \
    -q
fi

if should_run hosted-ui; then
  run_block hosted-ui
  if python3 - <<'PY' >/dev/null 2>&1
import fastapi  # noqa: F401
import httpx  # noqa: F401
import jinja2  # noqa: F401
import sqlalchemy  # noqa: F401
import uvicorn  # noqa: F401
PY
  then
    python3 scripts/test-home-kawaii-theme.py
    python3 scripts/test-private-registry-ui.py
    if [[ "${INFINITAS_SKIP_BROWSER_RUNTIME_TESTS:-0}" != "1" ]]; then
      PLAYWRIGHT_WRAPPER="${CODEX_HOME:-$HOME/.codex}/skills/playwright/scripts/playwright_cli.sh"
      if [[ -x "$PLAYWRIGHT_WRAPPER" ]]; then
        python3 scripts/test-home-auth-session-runtime.py
      elif [[ "${INFINITAS_REQUIRE_BROWSER_RUNTIME_TESTS:-0}" == "1" ]]; then
        echo "FAIL: browser runtime checks require Codex Playwright wrapper at $PLAYWRIGHT_WRAPPER" >&2
        exit 1
      else
        echo "SKIP: home auth browser runtime checks (missing Codex Playwright wrapper at $PLAYWRIGHT_WRAPPER)"
      fi
    fi
  elif [[ "${INFINITAS_REQUIRE_PRIVATE_REGISTRY_TESTS:-0}" == "1" ]]; then
    echo "FAIL: private registry UI checks require fastapi/httpx/jinja2/sqlalchemy/uvicorn in the current python environment" >&2
    exit 1
  else
    echo "SKIP: private registry UI checks (missing fastapi/httpx/jinja2/sqlalchemy/uvicorn in current python environment)"
  fi
fi

if should_run full-regression; then
  run_block full-regression
  python3 scripts/check-registry-sources.py
  python3 scripts/test-registry-refresh-policy.py
  python3 scripts/test-registry-snapshot-mirror.py
  python3 scripts/test-hosted-registry-source.py
  python3 scripts/check-policy-packs.py
  python3 scripts/test-policy-pack-loading.py
  python3 scripts/test-policy-evaluation-traces.py
  python3 scripts/test-break-glass-exceptions.py
  python3 scripts/test-team-governance-scopes.py
  python3 scripts/check-signing-config.py
  python3 scripts/validate-registry.py
  python3 scripts/test-policy-trace-docs.py
  python3 scripts/test-namespace-identity.py
  python3 scripts/check-registry-integrity.py
  python3 scripts/check-promotion-policy.py
  python3 scripts/test-review-governance.py
  python3 scripts/test-compat-regression.py
  python3 scripts/test-hosted-e2e-ci-contract.py
  python3 scripts/test-project-complete-state.py
  python3 scripts/test-settings-hardening.py
  python3 scripts/test-private-first-cutover-schema.py
  if python3 - <<'PY' >/dev/null 2>&1
import fastapi  # noqa: F401
import httpx  # noqa: F401
import jinja2  # noqa: F401
import sqlalchemy  # noqa: F401
import uvicorn  # noqa: F401
PY
  then
  python3 scripts/test-private-registry-access-api.py
  elif [[ "${INFINITAS_REQUIRE_PRIVATE_REGISTRY_TESTS:-0}" == "1" ]]; then
    echo "FAIL: private registry API checks require fastapi/httpx/jinja2/sqlalchemy/uvicorn in the current python environment" >&2
    exit 1
  else
    echo "SKIP: private registry API checks (missing fastapi/httpx/jinja2/sqlalchemy/uvicorn in current python environment)"
  fi
  if [[ "${INFINITAS_SKIP_INSTALLED_INTEGRITY_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-installed-skill-integrity.py
  python3 scripts/test-installed-integrity-report.py
  python3 scripts/test-installed-integrity-freshness.py
  python3 scripts/test-installed-integrity-history-retention.py
  python3 scripts/test-installed-integrity-stale-guardrails.py
  python3 scripts/test-install-manifest-compat.py
  fi
  if [[ "${INFINITAS_SKIP_COMPAT_PIPELINE_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-canonical-contracts.py
  python3 scripts/test-canonical-skill.py
  python3 scripts/test-new-skill.py
  python3 scripts/test-operate-infinitas-skill.py
  python3 scripts/test-render-skill.py
  python3 scripts/test-openclaw-export.py
  python3 scripts/test-codex-export.py
  python3 scripts/test-claude-export.py
  python3 scripts/test-compatibility-evidence.py
  if [[ "${INFINITAS_SKIP_RECORD_VERIFIED_SUPPORT_TESTS:-0}" != "1" ]]; then
    python3 scripts/test-record-verified-support.py
  fi
  python3 scripts/check-platform-contracts.py --max-age-days 30 --stale-policy fail
  python3 scripts/test-platform-contracts.py
  fi
  if [[ "${INFINITAS_SKIP_RELEASE_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-release-invariants.py
  fi
  if [[ "${INFINITAS_SKIP_ATTESTATION_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-attestation-verification.py
  fi
  if [[ "${INFINITAS_SKIP_DISTRIBUTION_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-distribution-install.py
  python3 scripts/test-hosted-registry-install.py
  fi
  if [[ "${INFINITAS_SKIP_AI_WRAPPER_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-discovery-index.py
  python3 scripts/test-resolve-skill.py
  python3 scripts/test-install-by-name.py
  python3 scripts/test-skill-update.py
  python3 scripts/test-explain-install.py
  python3 scripts/test-recommend-skill.py
  python3 scripts/test-ai-index.py
  python3 scripts/test-ai-pull.py
  python3 scripts/test-ai-publish.py
  python3 scripts/test-openclaw-import.py
  python3 scripts/test-search-docs.py
  python3 scripts/test-recommend-docs.py
  fi
  if [[ "${INFINITAS_SKIP_BOOTSTRAP_TESTS:-0}" != "1" ]]; then
  python3 scripts/test-signing-bootstrap.py
  python3 scripts/test-signing-readiness-report.py
  fi

  if [[ "${INFINITAS_SKIP_HOSTED_E2E_TESTS:-0}" != "1" ]]; then
  if python3 - <<'PY' >/dev/null 2>&1
import fastapi  # noqa: F401
import httpx  # noqa: F401
import jinja2  # noqa: F401
import sqlalchemy  # noqa: F401
import uvicorn  # noqa: F401
PY
  then
    python3 scripts/test-hosted-registry-e2e.py
  elif [[ "${INFINITAS_REQUIRE_HOSTED_E2E_TESTS:-0}" == "1" ]]; then
    echo "FAIL: hosted registry e2e checks require fastapi/httpx/jinja2/sqlalchemy/uvicorn in the current python environment" >&2
    exit 1
  else
    echo "SKIP: hosted registry e2e checks (missing fastapi/httpx/jinja2/sqlalchemy/uvicorn in current python environment)"
  fi
  fi

  while IFS= read -r dir; do
    [[ -n "$dir" ]] || continue
    scripts/check-skill.sh "$dir"
  done < <(find skills -mindepth 2 -maxdepth 2 -type d -exec test -f '{}/_meta.json' ';' -print | sort)

  before_catalog_norm="$(python3 - <<'PY'
import json
from pathlib import Path
for path in ['catalog/catalog.json','catalog/active.json','catalog/compatibility.json','catalog/registries.json','catalog/distributions.json','catalog/ai-index.json','catalog/discovery-index.json','catalog/inventory-export.json','catalog/audit-export.json']:
    p = Path(path)
    if not p.exists():
        continue
    data = json.loads(p.read_text(encoding='utf-8'))
    data.pop('generated_at', None)
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))
PY
)"
  scripts/build-catalog.sh >/dev/null
  python3 scripts/check-catalog-exports.py
  after_catalog_norm="$(python3 - <<'PY'
import json
from pathlib import Path
for path in ['catalog/catalog.json','catalog/active.json','catalog/compatibility.json','catalog/registries.json','catalog/distributions.json','catalog/ai-index.json','catalog/discovery-index.json','catalog/inventory-export.json','catalog/audit-export.json']:
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
    git --no-pager diff -- catalog/catalog.json catalog/active.json catalog/compatibility.json catalog/registries.json catalog/distributions.json catalog/ai-index.json catalog/discovery-index.json catalog/inventory-export.json catalog/audit-export.json || true
    exit 1
  fi
fi

echo "OK: requested registry check blocks passed (${BLOCKS[*]})"
