# Testing

## Preferred command layer

Use the repo-native `make` targets first:

```bash
make bootstrap
make test-fast
make test-full
make lint-maintained
```

Raw `uv` and script commands remain available below as fallback detail.

## Focused maintained-surface checks

Run the fast `pytest` tier first when touching the maintained CLI or hosted UI surfaces:

```bash
uv run pytest tests/integration/test_cli_release_state.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_ui.py -q
```

These files cover the maintained release CLI, the maintained server CLI surface, and the private-registry HTML route assembly without booting the full compatibility matrix.

## Legacy script wrappers

The historical script entrypoints remain available, but they now delegate to the focused `tests/integration/` checks:

```bash
uv run python3 scripts/test-infinitas-cli-release-state.py
uv run python3 scripts/test-infinitas-cli-server.py
uv run python3 scripts/test-private-registry-ui.py
```

Use these when following older docs or existing contributor workflows that still reference `scripts/test-*.py`.

## Named `check-all` blocks

`scripts/check-all.sh` accepts named blocks so you can choose a narrow or broad sweep:

```bash
scripts/check-all.sh focused-integration
scripts/check-all.sh hosted-ui
scripts/check-all.sh full-regression
scripts/check-all.sh focused-integration hosted-ui full-regression
```

Block intent:

- `focused-integration`: the fast maintained-surface `pytest` tier under `tests/integration/`
- `hosted-ui`: homepage/private-registry HTML coverage plus optional browser runtime checks
- `full-regression`: the broader compatibility, policy, catalog, install, and hosted-e2e matrix

Running `scripts/check-all.sh` with no arguments still executes all three blocks in order.
