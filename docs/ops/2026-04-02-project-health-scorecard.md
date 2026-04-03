---
audience: operators, release maintainers, contributors
owner: repository maintainers
source_of_truth: 2026-04-02 project health scorecard
last_reviewed: 2026-04-03
status: maintained
---

# 2026-04-02 Project Health Scorecard

## Verdict

Go for controlled release handling with a materially healthier maintained surface.

Compared with the 2026-04-01 scorecard and the earlier 2026-04-02 baseline snapshot, the repository
now has a stronger inner-loop path, clearer CI signaling, safer headroom in the heaviest maintained
orchestration files, a materially better story for discovery-memory regression coverage, and a new
operator-visible memory curation planning surface. The main remaining risks are the slower
legacy/full-regression path, the still-large maintained package surface outside the just-reduced
modules, and the lack of provider-side cleanup execution beyond the new local planning signals.

## Scores

| Category | Score | Evidence |
| --- | --- | --- |
| Release readiness | 9.8/10 | `make ci-fast` passed on 2026-04-03 (`14 passed in 23.43s`) after memory curation, recall evaluation expansion, and the `ai_index` split. |
| Maintainability | 9.6/10 | `recommendation.py` is 113 lines, `inspect.py` is 182 lines, and `ai_index.py` is now only 12 lines after the builder/validation extraction. |
| Operational clarity | 9.6/10 | `make doctor` passed on 2026-04-03 and operators now have both `infinitas server memory-health` and `infinitas server memory-curation` backed by local audit truth. |
| CI clarity | 9.6/10 | The repository now has the maintained fast gate plus a richer memory evaluation matrix that checks duplicate suppression and noisy recall stability. |

## Evidence Matrix

| Command | Status | Date | Notes |
| --- | --- | --- | --- |
| `make lint-maintained` | PASS | 2026-04-02 | Maintained lint baseline passed after the current optimization round. |
| `make test-fast` | PASS | 2026-04-02 | Maintained fast integration slice passed (`12 passed in 24.38s`). |
| `uv run pytest tests/integration/test_memory_evaluation_matrix.py tests/integration/test_cli_server_ops.py -q` | PASS | 2026-04-03 | Discovery memory evaluation fixtures and the maintained memory health/curation CLI coverage passed inside the current closeout sweep. |
| `uv run pytest tests/unit/memory/test_curation.py tests/unit/memory/test_context.py tests/unit/memory/test_experience.py tests/unit/memory/test_provider.py tests/unit/discovery/test_recommendation_memory.py tests/unit/discovery/test_inspect_memory.py tests/unit/discovery/test_ai_index_builder.py tests/unit/discovery/test_ai_index_validation.py tests/unit/server_memory/test_writeback.py tests/unit/server_ops/test_memory_health.py tests/unit/server_ops/test_memory_curation.py tests/integration/test_memory_evaluation_matrix.py tests/integration/test_cli_server_ops.py tests/integration/test_private_registry_memory_flow.py tests/integration/test_private_registry_ui.py tests/integration/test_dev_workflow.py -q` | PASS | 2026-04-03 | Expanded closeout matrix passed (`58 passed in 2.39s`). |
| `python3 scripts/test-ai-index.py` | PASS | 2026-04-03 | Temp-repo AI index validation and rebuild checks remained green after the builder/validation split. |
| `make ci-fast` | PASS | 2026-04-03 | Confirms the explicit CI fast gate (`lint-maintained` then `test-fast`) is still healthy after the current cleanup round (`14 passed in 23.43s`). |
| `python3 scripts/test-recommend-skill.py` | PASS | 2026-04-03 | Recommendation regression script remained green after the discovery split. |
| `python3 scripts/test-search-inspect.py` | PASS | 2026-04-03 | Search and inspect regression script remained green after the inspect split. |
| `python3 scripts/test-doc-governance.py` (`make doctor`) | PASS | 2026-04-03 | Documentation governance remained green after the new memory docs and scorecard updates. |

## Current Strengths

- Maintained command surface is clear and package-owned under `uv run infinitas ...`.
- Fast verification path remains reliable for inner-loop work and now has an explicit CI mirror in `make ci-fast`.
- Maintained lint signal is green, which is better than the 2026-04-01 baseline.
- Discovery memory seams now have dedicated unit coverage plus a fixture-backed evaluation matrix.
- Operators can inspect memory writeback health and curation candidates through maintained CLI commands without Memo0 access.
- The first six high-pressure maintained files or orchestration surfaces now have visibly better headroom:
  - `src/infinitas_skill/server/ops.py`: `542 -> 461`
  - `src/infinitas_skill/release/service.py`: `553 -> 333`
  - `server/ui/lifecycle.py`: `492 -> 460`
  - `src/infinitas_skill/discovery/recommendation.py`: `~730 -> 113`
  - `src/infinitas_skill/discovery/inspect.py`: `~412 -> 182`
  - `src/infinitas_skill/discovery/ai_index.py`: `534 -> 12`
- Operator documentation remains role-oriented and discoverable from `README.md` and `docs/ops/README.md`.
- New focused unit tests now protect the freshly extracted discovery, memory, and server helper seams.

## Current Risks

- `server/ui/lifecycle.py` is no longer at the edge, but it is still one of the larger maintained UI composition files.
- Long-running release verification remains script-heavy and slower than the maintained fast path.
- The repository still relies on a broader closeout matrix (`scripts/check-all.sh`) for highest-confidence regression coverage.
- Memory quality is now regression-tested and locally observable, but there is still no provider-side pruning, archival execution, or compaction job.
- The maintained package surface outside the just-optimized modules still deserves future cleanup attention.

## Optimization Delta

The current worktree completed these optimization steps by 2026-04-03:

1. Refreshed the project health baseline and operator entry docs.
2. Added a supported local cleanup path with `make clean-local`.
3. Split hosted server inspection orchestration into `inspection_summary.py` and `inspection_notifications.py`.
4. Split release-state decision helpers into `release_resolution.py` and `release_issues.py`.
5. Split lifecycle UI assembly into `lifecycle_state.py` and `lifecycle_actions.py`.
6. Aligned CI with the maintained fast gate by introducing `make ci-fast` and invoking it in `validate.yml`.
7. Split discovery recommendation memory orchestration into dedicated memory, ranking, and explanation modules.
8. Split discovery inspect memory orchestration into dedicated memory and view modules.
9. Added a fixture-backed memory evaluation matrix for discovery regressions.
10. Added a maintained `infinitas server memory-health` diagnostic backed by local audit events.
11. Added retrieval-time memory curation plus a maintained `infinitas server memory-curation` planning surface.
12. Expanded the memory evaluation matrix to cover duplicate suppression and noisy recall stability.
13. Split `src/infinitas_skill/discovery/ai_index.py` into dedicated builder and validation modules.

## Recommended Next Steps

1. Keep `make ci-fast`, `make lint-maintained`, and `make test-fast` as the default contributor gate.
2. Build provider-side pruning/archive execution on top of the new local curation planning signals.
3. Continue expanding recall-quality evaluation beyond discovery into longer-horizon memory usefulness metrics.
4. Continue reducing high-cost legacy/full-regression paths by moving more reusable logic into package-owned modules.
5. Revisit the remaining larger maintained files before they drift back toward budget ceilings.
