---
audience: contributors
owner: repository maintainers
source_of_truth: contribution guide
last_reviewed: 2026-06-01
status: maintained
---

# Contributing to infinitas

Thank you for your interest in improving infinitas! This document covers how to set up your environment, run tests, and submit changes.

## Quick Start

```bash
# 1. Clone and bootstrap
make bootstrap          # uv sync + npm install + npm run build

# 2. Verify everything works
make ci-fast            # lint + focused integration tests (~30s)
make test-e2e           # Playwright E2E tests (~5min)
make test-full          # full regression suite (~10min)
```

## Project Structure

| Directory | Purpose |
|---|---|
| `src/infinitas_skill/` | CLI and core library code |
| `server/` | FastAPI web application and UI |
| `tests/unit/` | Unit tests for discrete functions |
| `tests/integration/` | API and CLI workflow tests |
| `tests/e2e/` | Playwright browser automation tests |
| `scripts/` | Build, validation, and release scripts |
| `docs/` | Narrative documentation and ADRs |
| `skills/` | Skill definitions (active / archived / incubating) |

## Development Workflow

1. **Create a branch** from `main`
2. **Make your changes** with tests
3. **Run the fast gate**: `make ci-fast`
4. **Run the full suite** for significant changes: `make test-full`
5. **Lint your code**: `make lint-maintained`
6. **Open a pull request** — CI will run `validate.yml`

## Testing Guidelines

- Add unit tests for new pure functions
- Add integration tests for new API endpoints or CLI commands
- Add E2E tests for new user-facing UI workflows
- Maintain the line budgets enforced by `tests/integration/test_maintainability_budgets.py`

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

- Line length: 100
- Python target: 3.11+
- Enabled rules: `E, W, F, I, C90, S` (includes complexity and security checks)

Run `make lint-maintained` before committing.

## Documentation

- Update relevant docs in `docs/` for user-facing changes
- Update `README.md` if the quick-start or verification matrix changes
- Follow the metadata convention for maintained docs:
  ```yaml
  ---
  audience: ...
  owner: ...
  source_of_truth: ...
  last_reviewed: YYYY-MM-DD
  status: maintained
  ---
  ```

## Security

- Never commit API keys, tokens, or credentials
- Use environment variables for secrets
- Follow the security checklist in `SECURITY.md`

## Questions?

Open an issue or reach out to the maintainers. We review PRs within a few business days.
