.PHONY: bootstrap clean-local ci-fast test-fast test-full lint-maintained fmt-maintained doctor build-css watch-css

build-css:
	npm run build

watch-css:
	npm run watch

bootstrap:
	uv sync
	npm install
	npm run build

clean-local:
	find . \( -path './.venv' -o -path './.worktrees' \) -prune -o -type d -name '__pycache__' -exec rm -rf {} +
	find . \( -path './.venv' -o -path './.worktrees' \) -prune -o -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
	rm -rf .pytest_cache .ruff_cache .mypy_cache .hypothesis .tox .nox output/playwright
	find . \( -path './.worktrees' -o -path './.venv' \) -prune -o -maxdepth 2 -type d -name '*.egg-info' -exec rm -rf {} +
	git clean -fdX -- build 2>/dev/null || true

ci-fast: lint-maintained test-fast

test-fast:
	uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py -q

test-full:
	./scripts/check-all.sh

lint-maintained:
	uv run ruff check src/infinitas_skill server/ui server/app.py tests/integration tests/unit

fmt-maintained:
	uv run ruff format src/infinitas_skill server/ui server/app.py tests/integration tests/unit

doctor:
	uv run python3 scripts/test-doc-governance.py
