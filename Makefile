.PHONY: bootstrap clean-local ci-fast test-fast test-full test-e2e lint-maintained fmt-maintained doctor build-css watch-css typecheck

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
	uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py tests/integration/test_security_headers_and_csrf.py tests/integration/test_background_api.py tests/integration/test_auth_edge_cases.py tests/integration/test_search_api.py tests/integration/test_middleware.py tests/integration/test_activity_api.py tests/integration/test_db_utils.py tests/unit/server_access/test_authz.py tests/unit/server_ui/test_formatting.py tests/unit/server_ui/test_i18n.py tests/unit/server_ui/test_navigation.py tests/unit/server_ui/test_auth_state.py tests/unit/server_ui/test_console.py tests/unit/server_ui/test_home.py tests/unit/server_ui/test_session_bootstrap.py tests/unit/test_auth_utils.py tests/unit/skills/test_schema_version.py tests/unit/skills/test_canonical.py tests/unit/skills/test_render.py tests/unit/skills/test_openclaw.py tests/unit/server_shared/test_shared.py tests/unit/release/test_release_formatting.py tests/unit/release/test_release_resolution.py tests/unit/release/test_git_state.py tests/unit/release/test_release_issues.py tests/unit/policy/test_trace.py tests/unit/server/test_backup.py tests/unit/server/test_health.py tests/unit/compatibility/test_policy.py tests/unit/compatibility/test_contracts.py tests/unit/memory/test_scopes.py tests/unit/memory/test_config.py tests/unit/discovery/test_agent_support.py tests/unit/install/test_output.py tests/unit/openclaw/test_openclaw_contracts.py tests/unit/openclaw/test_plugins.py tests/unit/server_memory/test_curation_queue.py tests/unit/server_memory/test_retrieval_audit.py tests/integration/test_library_api.py tests/integration/test_publish_api.py tests/integration/test_object_tokens_api.py tests/integration/test_agent_preset_api.py -q

test-full:
	./scripts/check-all.sh

test-e2e:
	uv run pytest tests/e2e/ -q

lint-maintained:
	uv run ruff check src/infinitas_skill server/ui server/app.py tests/integration tests/unit

fmt-maintained:
	uv run ruff format src/infinitas_skill server/ui server/app.py tests/integration tests/unit

doctor:
	uv run python3 scripts/test-doc-governance.py

typecheck:
	uv run mypy src/infinitas_skill server/ --ignore-missing-imports
