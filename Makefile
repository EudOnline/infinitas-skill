.PHONY: bootstrap test-fast test-full lint-maintained fmt-maintained doctor

bootstrap:
	uv sync

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
