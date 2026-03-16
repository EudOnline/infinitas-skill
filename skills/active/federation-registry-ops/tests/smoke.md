# Smoke test

Scenario:

"A federated skill is missing from search results and the audit export seems to disagree with what the registry source configuration says. Figure out whether the problem is mirror visibility, federation mapping, or stale generated exports."

Expected guidance:

- inspect `config/registry-sources.json`
- compare `catalog/inventory-export.json` and `catalog/audit-export.json`
- use `scripts/search-skills.sh` and `scripts/inspect-skill.sh`
- rebuild generated artifacts only after identifying the source of drift
