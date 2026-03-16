# Trust Model

This repository is a **private skill registry**, not just a prompt scrapbook.

## Security assumptions

Skills may influence agents that can:
- read and write files
- execute shell commands
- call external APIs
- send messages

That makes every skill folder effectively **trusted code + trusted operating guidance**.

## Rules

### 1. Agents may contribute, but not auto-publish
Agent-created or agent-edited skills should land in `skills/incubating/` first.

### 2. `active/` is curated
Promotion into `skills/active/` should require a human check, even if the change is small.

### 3. Secrets never live in skills
API keys, cookies, bearer tokens, private SSH keys, and auth exports do not belong in this repo.

Repository-managed public signer entries in `config/allowed_signers` are allowed and expected for stable release verification.

### 4. Distribution is opt-in
A skill being present in the registry does not mean every agent should load it. Install or sync into local runtime directories deliberately.

### 5. Lineage matters
Track derivation with `_meta.json.derived_from` or a CHANGELOG entry so consumers can understand where a skill came from.

### 6. Federation is explicit policy, not an implied sync shortcut
- A registry may federate only when its configured trust tier, pinning policy, and namespace mapping pass validation.
- The working repository itself is never a federated upstream; `self` stays the writable source-of-truth.
- `mirror` registries are visible for operator inventory and backup, but they are not authoritative default resolver candidates.
- When publisher namespaces are mapped, tooling must preserve the original upstream publisher identity alongside the mapped local namespace.

Operational failure modes and recovery steps are documented in [docs/federation-operations.md](/Users/lvxiaoer/Documents/codeWork/infinitas-skill/.worktrees/codex-federation-trust-rules/docs/federation-operations.md). Treat that guide as the operator playbook when policy, exports, or provenance appear to disagree.

## Recommended runtime pattern

- Registry source: private Git repo
- Runtime install target: `~/.openclaw/skills` or `<workspace>/skills`
- Optional: generate catalogs and install/sync from those rather than loading the whole repo directly as a shared skills directory

## Hosted server pattern

- A hosted deployment may keep the writable source-of-truth repo on one trusted server
- Clients should install from immutable hosted artifacts, not from editable source folders
- GitHub or another forge can be a **one-way mirror** for backup and code review convenience
- Reverse-sync from the mirror back into the hosted source-of-truth repo is not trusted
- Federation rules belong in repository policy (`config/registry-sources.json`), not in ad-hoc environment variables or mirror hooks
