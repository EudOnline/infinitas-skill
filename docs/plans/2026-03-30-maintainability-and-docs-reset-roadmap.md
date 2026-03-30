# Maintainability And Docs Reset Roadmap

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reset `infinitas-skill` into a more maintainable architecture by intentionally breaking legacy script and document layout assumptions, then replacing them with a smaller, more coherent structure.

**Architecture:** Consolidate the repository around one Python package, one unified CLI, one fixture system, and one role-based documentation tree. Treat most current top-level scripts and ad hoc generated catalog files as legacy surfaces to be removed, not preserved. Use a staged migration so each phase ends in a shippable, internally consistent state even though compatibility is intentionally broken.

**Tech Stack:** Python package refactor, unified CLI entrypoints, `pytest`-style shared fixtures, generated reference docs, role-based Markdown docs, CI validation, repo-level architecture decision records.

---

### Phase 0: Freeze legacy growth before refactoring

**Outcome:** Stop the codebase from getting harder to untangle while the reset is in flight.

**Breaking posture:**
- No promise that new work will continue to land in `scripts/` or `docs/` using the current layout.
- New features should target the future package/doc structure only.

**Tasks:**
1. Mark the current `scripts/` directory as legacy in contributor docs.
2. Add a temporary policy that no new top-level script may be added without explicit architectural approval.
3. Add a temporary policy that no new long-lived doc may be added outside the future doc IA.
4. Create a short ADR that states the repository is entering a breaking maintainability reset.
5. Define the future top-level structure:
   - `src/infinitas_skill/`
   - `tests/`
   - `docs/guide/`
   - `docs/reference/`
   - `docs/ops/`
   - `docs/archive/`
6. Identify a hard cutoff date for deleting legacy aliases instead of maintaining them forever.

**Exit criteria:**
- The target architecture is written down.
- The team has agreed that backward compatibility is not a constraint for this reset.

---

### Phase 1: Replace script sprawl with one package and one CLI

**Outcome:** The repo stops behaving like a loose pile of executable files and starts behaving like one product/toolchain.

**Current pain addressed:**
- `scripts/` has too many unrelated entrypoints.
- Shared logic is mixed with shell wrappers and tests.
- Discoverability is poor because the command surface is fragmented.

**Target structure:**
- `src/infinitas_skill/cli/`
- `src/infinitas_skill/compatibility/`
- `src/infinitas_skill/release/`
- `src/infinitas_skill/install/`
- `src/infinitas_skill/registry/`
- `src/infinitas_skill/policy/`
- `src/infinitas_skill/server/`

**Tasks:**
1. Introduce a real package root under `src/infinitas_skill/`.
2. Create a unified CLI such as `infinitas`.
3. Map current command families into subcommands:
   - `infinitas compatibility ...`
   - `infinitas release ...`
   - `infinitas install ...`
   - `infinitas registry ...`
   - `infinitas policy ...`
   - `infinitas server ...`
4. Move reusable libs out of `scripts/*_lib.py` into the package.
5. Convert only a thin set of shell scripts into compatibility shims for one release cycle, or skip shims entirely if the team wants a hard cut.
6. Delete redundant or single-purpose shell wrappers that no longer add value after the CLI exists.
7. Generate a command map from old names to new names for internal migration.

**Explicitly allowed breaking changes:**
- Old script names can disappear.
- CLI flags can be redesigned for consistency.
- Shell wrappers can be removed instead of preserved.

**Exit criteria:**
- Every maintained command is reachable from one CLI.
- Shared logic no longer lives directly under `scripts/`.

---

### Phase 2: Replace test script duplication with shared fixtures and test tiers

**Outcome:** New behavior is tested through reusable factories and tiered suites instead of one-off Python scripts that each rebuild their own world.

**Current pain addressed:**
- Repeated fixture setup across release, attestation, bootstrap, AI index, install, and registry tests.
- Slow and brittle full-stack checks because each script bootstraps slightly different repos.
- High maintenance cost whenever one shared invariant changes.

**Target structure:**
- `tests/unit/`
- `tests/integration/`
- `tests/e2e/`
- `tests/fixtures/`
- `tests/helpers/`

**Tasks:**
1. Move from ad hoc `scripts/test-*.py` layout toward `pytest`.
2. Build shared fixture factories for:
   - temporary repos
   - release fixtures
   - platform evidence
   - signer/bootstrap state
   - hosted registry setup
3. Replace copy-pasted scaffold helpers with fixture builders.
4. Split the current giant `check-all.sh` path into named suites:
   - fast unit
   - integration
   - release/attestation
   - hosted/e2e
5. Keep one top-level orchestrator, but make it dispatch named suites rather than manually enumerating hundreds of files.
6. Convert generated fixture evidence into declared sources, then materialize them during tests instead of hardcoding every JSON manually.
7. Add timing metrics so slow suites can be profiled and optimized deliberately.

**Explicitly allowed breaking changes:**
- Existing test file names can be replaced.
- The old `scripts/test-*.py` convention does not need to survive.
- CI command names can change.

**Exit criteria:**
- Changing one shared release invariant no longer requires touching many separate test scripts.
- Engineers can run targeted suites without understanding the entire repo.

---

### Phase 3: Split source-of-truth data from generated artifacts

**Outcome:** The repo becomes clear about what humans edit and what machines generate.

**Current pain addressed:**
- `catalog/` is partly product output, partly test fixture, partly committed golden data.
- Generated files create constant dirty working trees and confusing review noise.

**Target policy:**
- Human-edited facts stay in source directories.
- Generated registry artifacts live in a build/output directory by default.
- Only a small set of golden fixtures remain committed.

**Tasks:**
1. Define the authoritative input directories for source facts.
2. Move generated outputs to something like `.artifacts/registry/` or `build/registry/`.
3. Keep only the minimal committed golden catalog fixtures required for tests and examples.
4. Update tests to build artifacts on demand instead of assuming committed generated files are current.
5. Add a dedicated golden-fixture regeneration command for reviewers.
6. Separate fixture evidence used only by tests from evidence treated as canonical registry content.

**Explicitly allowed breaking changes:**
- Committed catalog outputs can disappear.
- Review workflows can stop diffing generated artifacts by default.
- Any tooling that assumes `catalog/*.json` is always committed can be removed.

**Exit criteria:**
- Dirty working trees are not dominated by generated files.
- Review diffs focus on source facts and logic changes.

---

### Phase 4: Rebuild documentation around audiences instead of history

**Outcome:** Docs become navigable by role and task, while older design/planning material becomes archived context instead of primary guidance.

**Current pain addressed:**
- Too many docs at the same level.
- Plans, guides, references, and historical notes are mixed together.
- Readers cannot quickly tell what is canonical vs archival.

**Target doc IA:**
- `docs/guide/`
- `docs/reference/`
- `docs/ops/`
- `docs/archive/`
- `docs/adr/`

**Tasks:**
1. Rewrite `README.md` as a true entry page only.
2. Move active operator workflows into `docs/ops/`.
3. Move stable API/schema/CLI reference into `docs/reference/`.
4. Move human onboarding and conceptual docs into `docs/guide/`.
5. Move `docs/plans/` and superseded design narratives into `docs/archive/`.
6. Add front-matter metadata to every maintained doc:
   - `audience`
   - `owner`
   - `source_of_truth`
   - `last_reviewed`
   - `status`
7. Add ADRs for durable decisions such as:
   - private-first architecture
   - release trust model
   - platform compatibility freshness gate
   - generated artifact policy
8. Generate CLI and schema reference docs from code instead of hand-maintaining them.
9. Add three fixed architecture diagrams:
   - release flow
   - compatibility freshness flow
   - registry generation flow

**Explicitly allowed breaking changes:**
- Existing doc URLs and filenames can change.
- `docs/plans/` no longer needs to be treated as a current-user entrypoint.
- Old duplicated explanations can be deleted instead of preserved.

**Exit criteria:**
- Every doc has a clear audience and status.
- A new engineer can find the canonical operator guide and CLI reference in under five minutes.

---

### Phase 5: Tighten architecture boundaries, then consider repo split

**Outcome:** The repository reflects real subsystem boundaries instead of accumulated history.

**Current pain addressed:**
- Registry toolchain, hosted control plane, installer, and AI-facing exports all live together.
- Ownership boundaries are unclear.
- Refactors in one area spill across too much of the tree.

**Tasks:**
1. Draw clear module boundaries between:
   - core domain logic
   - CLI layer
   - hosted server
   - tests
2. Enforce import boundaries inside the package.
3. Move shared contracts and schemas into a small clearly owned layer.
4. Decide whether to stop here with one cleaned repo, or split into:
   - `infinitas-registry-core`
   - `infinitas-hosted-control-plane`
5. If splitting, extract the core first and make the hosted server consume it as a dependency.

**Explicitly allowed breaking changes:**
- Internal imports can be rewritten aggressively.
- The hosted app can stop importing registry implementation details directly.
- A future multi-repo cut is allowed.

**Exit criteria:**
- Each subsystem has an obvious owner and dependency direction.
- Cross-cutting changes are meaningfully rarer than today.

---

### Delivery cadence

**Week 1-2**
- Phase 0
- Phase 1 design and skeleton
- ADRs for the reset

**Week 3-4**
- Phase 1 execution
- Introduce unified CLI
- Start deleting legacy wrappers

**Week 5-6**
- Phase 2 execution
- Shared fixtures
- New suite layout

**Week 7**
- Phase 3 execution
- Generated artifact policy change

**Week 8**
- Phase 4 execution
- Doc IA cutover
- Decision on Phase 5 repo boundary hardening

---

### Success metrics

- Top-level maintained executable entrypoints drop by at least 70%.
- Shared test fixture helpers replace at least 80% of duplicated repo/bootstrap scaffolding.
- `README.md` shrinks into a navigation page instead of a knowledge dump.
- Maintained docs are fewer, shorter, and tagged with audience/status metadata.
- Generated artifact noise in normal development drops sharply.
- New contributors can answer “which command do I run?” and “which doc is canonical?” without tribal knowledge.

---

### Recommended first execution slice

If you want to start immediately, do this first:

1. Write an ADR that the repository is entering a breaking maintainability reset.
2. Create `src/infinitas_skill/` and one `infinitas` CLI skeleton.
3. Move one vertical slice end-to-end:
   - platform compatibility contract loading
   - compatibility freshness policy
   - release preflight gate
4. Replace the old entrypoints for that slice with thin wrappers or delete them outright.
5. Convert the release fixture scaffolding into shared test fixtures.
6. Cut `README.md` down to a navigation page and move the rest into role-based docs.

This gives you one real vertical proof before you spend weeks reorganizing everything else.
