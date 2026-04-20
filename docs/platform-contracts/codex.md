---
audience: contributors, reviewers, compatibility maintainers
owner: repository maintainers
source_of_truth: legacy platform contract annex
last_reviewed: 2026-04-21
status: legacy
---

# Codex Platform Contract

## Stable assumptions
- Codex supports Agent Skills as directories containing `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, and `agents/openai.yaml`.
- Codex uses progressive disclosure: it starts from skill metadata and reads full `SKILL.md` only when the skill is selected.
- Repository skills are discovered from `.agents/skills` locations from the current working directory up to the repository root, plus user/admin/system locations.
- `AGENTS.md` remains an explicit repository-level instruction surface for Codex behavior.

## Volatile assumptions
- Skill discovery precedence, system skill inventory, and optional `agents/openai.yaml` fields may evolve.
- Hosted API Skills and local Codex runtime skills share the same family of concepts but not identical attachment mechanics.
- Codex cloud environment features such as internet access and approvals continue to evolve and may affect how skills are executed or verified.

## Official sources
- https://developers.openai.com/codex/skills
- https://developers.openai.com/codex/guides/agents-md
- https://developers.openai.com/codex/cloud

## Last verified
2026-04-13

## Verification steps
- Confirm the Agent Skills page still requires `SKILL.md` with `name` and `description`, and still documents optional support directories.
- Confirm the skill discovery locations still include `.agents/skills` in repository ancestry plus user/admin/system scopes.
- Confirm the AGENTS guide still documents repository instructions as a supported customization surface.

## Known gaps
- OpenAI currently exposes both Codex runtime skills and API-hosted skills; this repository targets the local/runtime-oriented layout first.
- Some hosted-shell constraints, upload limits, or management APIs may change independently from the Codex CLI/app skill format.
