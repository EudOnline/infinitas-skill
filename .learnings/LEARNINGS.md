# Learnings

## [LRN-20260713-001] correction

**Logged**: 2026-07-13T17:00:00Z
**Priority**: high
**Status**: pending
**Area**: backend

### Summary
The infinitas-skill project is unpublished and does not require backward compatibility; cleanliness takes priority over preserving internal or legacy contracts.

### Details
The earlier audit treated legacy schemas, internal re-exports, script wrappers, and migration history as compatibility constraints. The user clarified that the project has not been released, so those constraints should not drive the architecture. Future refactoring plans should prefer hard cutovers, deletion, migration squashing, and one canonical entrypoint unless specific development data must be preserved.

### Suggested Action
Design the cleanup around a clean target architecture and explicitly ask only whether current local database/data artifacts must survive the reset.

### Metadata
- Source: user_feedback
- Related Files: server/models.py, src/infinitas_skill/install/workflows.py, alembic/versions, scripts
- Tags: compatibility, cleanup, hard-cutover, architecture
- Pattern-Key: architecture.unreleased_no_compatibility
- Recurrence-Count: 1
- First-Seen: 2026-07-13
- Last-Seen: 2026-07-13

---

## [LRN-20260714-002] best_practice

**Logged**: 2026-07-14T11:50:00Z
**Priority**: medium
**Status**: resolved
**Area**: backend

### Summary

After moving a function to a single canonical owner, scan the whole repository for imports from the previous owner before running broad CLI tests.

### Details

`evaluate_review_state` moved from `policy.reviews` to `policy.review_evaluation`, but one promotion-report import retained the former owner. Because the top-level CLI imports the policy service eagerly, that single stale import made otherwise unrelated install and release commands fail at startup.

### Suggested Action

Pair ownership moves with an exact-symbol `rg` scan and a direct module-import smoke test before broader regression suites.

### Metadata

- Source: error
- Related Files: src/infinitas_skill/policy/promotion_report.py, src/infinitas_skill/policy/review_evaluation.py
- Tags: ownership, imports, refactor, cli
- Pattern-Key: architecture.symbol_owner_scan
- Recurrence-Count: 1
- First-Seen: 2026-07-14
- Last-Seen: 2026-07-14

### Resolution

- **Resolved**: 2026-07-14T11:50:00Z
- **Notes**: Updated the remaining import and added exact-symbol scanning to the refactor workflow.

---

## [LRN-20260721-001] knowledge_gap

**Logged**: 2026-07-21T11:50:00Z
**Priority**: medium
**Status**: resolved
**Area**: docs

### Summary

OpenClaw and Claude Code platform contracts drifted from current official Skill semantics.

### Details

ClawHub now accepts ordinary files and applies MIT-0 at publish time, while Claude Code now documents native Agent Skills rather than only a subagent adapter model. The repository had retained an obsolete text-only ClawHub gate, invented per-skill license metadata, and understated Claude's native skill surface.

### Suggested Action

Verify compatibility contracts against primary documentation before refreshing evidence, and keep platform-specific extensions separate from the portable `SKILL.md` contract.

### Metadata

- Source: error
- Related Files: profiles/openclaw.json, docs/platform-contracts/openclaw.md, docs/platform-contracts/claude.md
- Tags: platform-contract, openclaw, claude-code, compatibility

### Resolution

- **Resolved**: 2026-07-21T11:50:00Z
- **Notes**: Updated all three platform contract review dates, corrected the OpenClaw validator and renderer, and refreshed the four Active Skill OpenClaw export checks.

---

## [LRN-20260722-001] best_practice

**Logged**: 2026-07-22T18:22:00Z
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary

Live SQLite backups must use SQLite's online backup API and validate the resulting snapshot, rather than copying the database file directly.

### Details

A plain filesystem copy can race active transactions or omit WAL state. The online backup API produces a transactionally consistent snapshot while the service remains available, and `PRAGMA integrity_check` verifies both the completed backup and the restored copy.

### Suggested Action

Keep database-specific snapshot logic inside the backup implementation and require full integrity checks during backup creation and restore rehearsal.

### Metadata

- Source: audit
- Related Files: src/infinitas_skill/server/backup.py, src/infinitas_skill/server/restore.py
- Tags: sqlite, backup, restore, consistency
- Pattern-Key: infra.sqlite_online_backup
- Recurrence-Count: 1
- First-Seen: 2026-07-22
- Last-Seen: 2026-07-22

---
