#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy src/infinitas_skill server
.venv/bin/infinitas policy check-packs
find . -maxdepth 1 -type f -name '.coverage*' -delete
.venv/bin/pytest tests/unit tests/integration tests/security tests/performance --cov-fail-under=64
.venv/bin/pytest tests/e2e
.venv/bin/pytest tests/integration/test_alembic_metadata.py -q --override-ini=addopts=
.venv/bin/python scripts/generate-openapi.py --check
.venv/bin/pip-audit
npm audit --registry=https://registry.npmjs.org --audit-level=high
npm run build
