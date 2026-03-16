# Recommendation Comparative Signals Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend recommendation outputs with stable comparative quality, confidence, freshness, and compatibility signals so agents can explain why one eligible skill outranks another.

**Architecture:** Keep the current deterministic recommendation ordering in `scripts/recommend_skill_lib.py` and add additive comparison metadata rather than rewriting the scoring model. Generate comparison fields from the already surfaced ranking inputs, expose a small confidence view plus per-result comparative signals, and document how agents should read those fields when choosing between multiple skills.

**Tech Stack:** Python 3.11 helper libraries, Bash CLI wrapper output, existing `scripts/test-*.py` regression style, and Markdown AI docs.

---

## Preconditions

- Work in `/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules`.
- Use `@superpowers:test-driven-development` before each production change.
- Use `@superpowers:verification-before-completion` before claiming completion or committing.
- Keep 12-07 additive:
  - do not rewrite recommendation ordering unless a focused regression proves it is necessary
  - do not introduce a new schema file unless the recommendation contract is clearly stable enough to justify it
  - do not broaden into the stable usage guide; that belongs to 12-09

## Scope decisions

- Recommended approach: preserve the current deterministic score and add comparison metadata derived from existing ranking factors.
- Recommended approach: expose both per-result comparison fields and top-level winner confidence so agents can reason about the top choice and the nearby alternatives.
- Recommended approach: keep confidence heuristic simple and reviewable, based on score separation plus factor strength, instead of fuzzy natural-language judgments.
- Rejected approach: replace the ranking formula during 12-07, because ECO-06 asks for better comparative signals, not a new ranking engine.
- Rejected approach: add only docs with no machine-readable fields, because the requirement explicitly calls for recommendation outputs to expose the signals.

### Task 1: Add failing comparative recommendation coverage

**Files:**
- Modify: `scripts/test-recommend-skill.py`
- Modify: `scripts/test-ai-workflow-drills.py`

**Step 1: Add failing comparison assertions to recommendation tests**

Extend `scripts/test-recommend-skill.py` so recommendation results now assert:

- each ranked result includes `confidence`
- each ranked result includes `comparative_signals`
- `confidence` exposes a stable level plus machine-readable reasons
- `comparative_signals` exposes rank and comparison-to-top fields for:
  - quality
  - verification freshness
  - compatibility
  - score gap

Also assert the top-level recommendation explanation includes winner confidence / comparison context when a runner-up exists.

**Step 2: Add one drill assertion**

Extend `scripts/test-ai-workflow-drills.py` so the recommend drill checks that public workflow output includes the new comparative fields without opening internals.

**Step 3: Run focused tests to verify RED**

Run:

```bash
python3 scripts/test-recommend-skill.py
python3 scripts/test-ai-workflow-drills.py
```

Expected: FAIL because current recommendation output does not expose confidence or additive comparative signals.

### Task 2: Implement additive comparative signals in recommendation output

**Files:**
- Modify: `scripts/recommend_skill_lib.py`

**Step 1: Implement comparison helpers**

Add small helpers that:

- normalize confidence from score margin plus factor strength
- compare each result against the winner
- produce stable, reviewable fields instead of prose-only judgments

Recommended output shape:

```python
result['confidence'] = {
    'level': 'high',
    'reasons': ['strong task-term match', 'clear score margin over runner-up'],
}
result['comparative_signals'] = {
    'rank': 1,
    'score_gap_from_top': 0,
    'quality_gap_from_top': 0,
    'verification_freshness_gap_from_top': 0,
    'compatibility_gap_from_top': 'same',
}
```

Top-level `explanation` should also expose additive comparison context such as:

- `winner_confidence`
- `score_gap_to_runner_up`
- `comparison_summary`

**Step 2: Keep the ranking logic stable**

Do not reorder factors unless the red tests prove a current gap. This slice is about surfacing comparisons, not changing winners.

**Step 3: Re-run focused tests**

Run:

```bash
python3 scripts/test-recommend-skill.py
python3 scripts/test-ai-workflow-drills.py
```

Expected: PASS.

### Task 3: Document the comparative recommendation contract

**Files:**
- Modify: `docs/ai/recommend.md`
- Modify: `docs/ai/search-and-inspect.md`
- Modify: `docs/ai/workflow-drills.md`

**Step 1: Update recommendation docs**

Document:

- what `confidence.level` means
- how to read `comparative_signals`
- that recommendation remains advisory even when confidence is high
- that agents should inspect before install when provenance or trust matters

Keep the docs aligned with the actual field names emitted by the wrapper.

**Step 2: Re-run docs and drill checks**

Run:

```bash
python3 scripts/test-recommend-docs.py
python3 scripts/test-search-docs.py
python3 scripts/test-ai-workflow-drills.py
```

Expected: PASS.

### Task 4: Final verification and commit

**Step 1: Run the final 12-07 regression set**

Run:

```bash
python3 scripts/test-recommend-skill.py
python3 scripts/test-ai-workflow-drills.py
python3 scripts/test-recommend-docs.py
python3 scripts/test-search-docs.py
python3 scripts/test-search-inspect.py
python3 scripts/test-install-by-name.py
python3 scripts/test-ai-pull.py
python3 scripts/test-ai-publish.py
git diff --check
```

Expected: PASS.

**Step 2: Commit**

```bash
git add docs/ai/recommend.md docs/ai/search-and-inspect.md docs/ai/workflow-drills.md \
  docs/plans/2026-03-16-recommendation-comparative-signals.md \
  scripts/recommend_skill_lib.py scripts/test-recommend-skill.py scripts/test-ai-workflow-drills.py
git commit -m "feat: add recommendation comparative signals"
```
