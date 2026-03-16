# Smoke test

Scenario:

"A new registry skill is ready for other agents. Validate it, move it through review and promotion, create immutable release artifacts locally, and refresh compatibility evidence without pushing anything to the remote yet."

Expected guidance:

- run `scripts/check-skill.sh`
- request or record review before promotion
- use `scripts/promote-skill.sh` only after approval
- use `scripts/release-skill.sh ... --create-tag --write-provenance`
- rebuild catalogs and optionally run `python3 scripts/record-verified-support.py`
