# Policy Evaluation Traces Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add explainable, machine-readable policy evaluation traces for validation, promotion, and release-readiness flows without breaking existing CLI behavior.

**Architecture:** Extend the policy-pack loader so commands can see not only the effective domain payload but also the ordered policy sources that produced it. Build a small shared trace helper for consistent JSON shape and optional human-readable debug rendering, then thread that helper through promotion policy checks, release readiness checks, and registry validation in an additive way.

**Tech Stack:** Python 3.11 CLI scripts, JSON policy/config files, existing policy-pack loader, script-style regression tests in `scripts/test-*.py`, and Markdown docs.

---

## Preconditions

- Work in a dedicated worktree.
- Use `@superpowers:test-driven-development` for each behavior change.
- Use `@superpowers:verification-before-completion` before any completion claim or commit.
- Keep current text-mode success/failure behavior compatible for `scripts/check-all.sh` and existing shell callers.
- Make policy traces additive: do not remove current `errors`, `warnings`, `review_gate_pass`, or release-state fields.

## Scope decisions

- Recommended approach: add `policy_trace` / `policy_traces` to JSON outputs and add an opt-in `--debug-policy` text view.
- Rejected approach: replace current command output with trace-only output, because that would break existing checks and shell workflows.
- Rejected approach: implement field-level provenance introspection for every effective policy value; 11-02 only needs ordered source visibility and decision traces, not per-key provenance.
- Initial trace fields should be stable and small:
  - `domain`
  - `decision`
  - `summary`
  - `effective_sources`
  - `applied_rules`
  - `blocking_rules`
  - `reasons`
  - `next_actions`
- First commands in scope:
  - `scripts/check-promotion-policy.py`
  - `scripts/check-release-state.py`
  - `scripts/validate-registry.py`

### Task 1: Add failing policy-trace coverage for promotion, release, and validation

**Files:**
- Create: `scripts/test-policy-evaluation-traces.py`
- Reference: `scripts/check-promotion-policy.py`
- Reference: `scripts/check-release-state.py`
- Reference: `scripts/validate-registry.py`
- Reference: `scripts/test-review-governance.py`
- Reference: `scripts/test-release-invariants.py`

**Step 1: Write the failing test**

Create `scripts/test-policy-evaluation-traces.py` with focused scenarios that:

- run `scripts/check-promotion-policy.py --json --as-active <skill>`
- expect JSON containing:
  - `policy_trace.domain == "promotion_policy"`
  - `policy_trace.decision`
  - `policy_trace.effective_sources`
  - `policy_trace.applied_rules`
- run `scripts/check-release-state.py <skill> --json`
- expect JSON containing:
  - `policy_trace.domain == "release_policy"`
  - `policy_trace.reasons`
  - `policy_trace.blocking_rules`
- run `scripts/validate-registry.py --json`
- expect JSON containing:
  - `policy_traces`
  - at least one trace for `namespace_policy`
  - no raw pack filesystem internals beyond explicit source paths
- seed at least one failing promotion/release or namespace-policy case in a temp repo and assert the trace includes blocking reasons, not only a failed exit code

Use assertion shapes like:

```python
payload = json.loads(run([sys.executable, str(repo / 'scripts' / 'check-promotion-policy.py'), '--json', '--as-active', str(skill_dir)], cwd=repo).stdout)
trace = payload.get('policy_trace') or {}
if trace.get('domain') != 'promotion_policy':
    fail(f"expected promotion_policy trace, got {trace.get('domain')!r}")
for key in ['decision', 'effective_sources', 'applied_rules']:
    if key not in trace:
        fail(f'missing policy trace field {key!r}')
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3 scripts/test-policy-evaluation-traces.py
```

Expected: FAIL because promotion/validation commands do not expose trace JSON yet.

**Step 3: Commit**

```bash
git add scripts/test-policy-evaluation-traces.py
git commit -m "test: add policy evaluation trace coverage"
```

### Task 2: Extend policy-pack loading with source resolution and add a shared trace helper

**Files:**
- Modify: `scripts/policy_pack_lib.py`
- Create: `scripts/policy_trace_lib.py`
- Modify: `scripts/test-policy-pack-loading.py`

**Step 1: Write the failing loader assertion**

Extend `scripts/test-policy-pack-loading.py` so it also asserts a resolution helper can report:

- ordered `effective_sources`
- which packs contributed to the domain
- whether a repository-local override was applied last

Use assertion shapes like:

```python
resolution = load_policy_domain_resolution(repo, 'signing')
sources = resolution.get('effective_sources') or []
if [item.get('kind') for item in sources] != ['pack', 'pack', 'local_override']:
    fail(f'unexpected policy source order: {sources!r}')
```

**Step 2: Run the focused loader test to verify it fails**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
```

Expected: FAIL because source-resolution metadata is not exposed yet.

**Step 3: Implement the minimal shared helpers**

Update `scripts/policy_pack_lib.py` so it exposes:

```python
def load_policy_domain_resolution(root: Path, domain: str) -> dict:
    ...
```

with:

- `domain`
- `effective`
- `effective_sources`

Create `scripts/policy_trace_lib.py` with helpers like:

```python
def build_policy_trace(...): ...
def render_policy_trace(trace: dict) -> str: ...
```

Keep the trace schema stable and additive.

**Step 4: Re-run the focused tests**

Run:

```bash
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-check-policy-packs.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/policy_pack_lib.py scripts/policy_trace_lib.py scripts/test-policy-pack-loading.py
git commit -m "feat: add policy source resolution and shared trace helpers"
```

### Task 3: Add policy traces to promotion and release readiness commands

**Files:**
- Modify: `scripts/check-promotion-policy.py`
- Modify: `scripts/review_lib.py`
- Modify: `scripts/check-release-state.py`
- Modify: `scripts/release_lib.py`
- Modify: `scripts/test-policy-evaluation-traces.py`

**Step 1: Implement promotion trace collection**

Add a JSON mode plus trace payload to `scripts/check-promotion-policy.py`:

- `--json`
- `--debug-policy`

The payload should include:

- existing review/evaluation facts
- `policy_trace`

The trace should summarize:

- whether promotion is allowed
- required approvals/groups
- missing groups or blocking rejections
- active requirement failures such as missing changelog or owner
- effective policy sources from `promotion_policy`

**Step 2: Implement release trace collection**

Update `scripts/check-release-state.py` / `scripts/release_lib.py` so JSON output includes:

- existing `errors` / `warnings`
- `policy_trace`

The trace should summarize:

- whether release is ready
- blocking rules for dirty tree, upstream drift, tag verification, remote tag state, and namespace authorization
- effective policy sources from `signing` and `namespace_policy` when relevant

**Step 3: Re-run the focused trace test**

Run:

```bash
python3 scripts/test-policy-evaluation-traces.py
```

Expected: at least the promotion and release assertions PASS; validation may still fail until Task 4 is finished.

**Step 4: Run focused compatibility regressions**

Run:

```bash
python3 scripts/test-review-governance.py
python3 scripts/test-release-invariants.py
python3 scripts/test-ci-attestation-policy.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/check-promotion-policy.py scripts/review_lib.py scripts/check-release-state.py scripts/release_lib.py scripts/test-policy-evaluation-traces.py
git commit -m "feat: expose policy traces for promotion and release checks"
```

### Task 4: Add policy traces to registry validation and document the debug flow

**Files:**
- Modify: `scripts/validate-registry.py`
- Modify: `scripts/check-skill.sh`
- Create: `scripts/test-policy-trace-docs.py`
- Modify: `docs/policy-packs.md`
- Modify: `README.md`

**Step 1: Implement validation trace output**

Add:

- `--json`
- `--debug-policy`

to `scripts/validate-registry.py`.

Expose:

- overall validation result
- per-skill validation errors
- `policy_traces`

At minimum, each registry-managed skill should emit a namespace-policy trace explaining:

- publisher claim acceptance or rejection
- whether a transfer was required
- competing claims or authorization issues
- effective policy sources from `namespace_policy`

Keep current plain-text validation output unchanged unless `--debug-policy` is requested.

**Step 2: Add docs regression coverage**

Create `scripts/test-policy-trace-docs.py` so it asserts:

- `README.md` mentions policy trace support
- `docs/policy-packs.md` mentions `--debug-policy`
- docs describe `policy_trace` / `policy_traces` and ordered source visibility

**Step 3: Re-run focused tests**

Run:

```bash
python3 scripts/test-policy-evaluation-traces.py
python3 scripts/test-policy-trace-docs.py
```

Expected: PASS.

**Step 4: Commit**

```bash
git add scripts/validate-registry.py scripts/check-skill.sh docs/policy-packs.md README.md scripts/test-policy-trace-docs.py
git commit -m "feat: add policy traces for registry validation"
```

### Task 5: Run final 11-02 verification

**Files:**
- No new files expected

**Step 1: Run focused trace checks**

Run:

```bash
python3 scripts/test-policy-evaluation-traces.py
python3 scripts/test-policy-pack-loading.py
python3 scripts/test-check-policy-packs.py
python3 scripts/test-policy-trace-docs.py
```

Expected: PASS.

**Step 2: Run touched compatibility regressions**

Run:

```bash
python3 scripts/test-review-governance.py
python3 scripts/test-release-invariants.py
python3 scripts/test-ci-attestation-policy.py
python3 scripts/test-namespace-identity.py
python3 scripts/test-hosted-registry-source.py
```

Expected: PASS.

**Step 3: Run full repository verification**

Run:

```bash
scripts/check-all.sh
```

Expected: PASS, except the existing hosted E2E dependency skip remains acceptable if optional hosted-stack packages are absent.

**Step 4: Inspect final branch state**

Run:

```bash
git status --short
git log --oneline -6
```

Expected:

- only intended 11-02 files changed
- commits are easy to review by task

**Step 5: Decide branch completion flow**

After verification, use `@superpowers:finishing-a-development-branch` to choose whether to merge locally, push a PR, keep the branch, or discard it.
