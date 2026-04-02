# Publish and Release

Private-first publishing is no longer a shell pipeline around review, promotion, and publish scripts.

The supported flow is:

1. create or load a skill record
2. create a draft
3. patch the draft until ready
4. seal the draft into an immutable version
5. create a release for that version
6. let the worker materialize release artifacts
7. create exposures for `private`, `grant`, or `public`
8. approve the public review case when public exposure is required

## CLI entrypoint

Use `uv run infinitas registry` against the hosted API.

Examples:

```bash
uv run infinitas registry skills create \
  --slug demo-skill \
  --display-name "Demo Skill" \
  --summary "Private-first demo skill"

uv run infinitas registry drafts create 1 \
  --content-ref 'git+https://example.com/demo-skill.git#<commit>' \
  --metadata-json '{"entrypoint":"SKILL.md","manifest":{"name":"demo-skill","version":"0.1.0"}}'

uv run infinitas registry drafts seal 1 --version 0.1.0
uv run infinitas registry releases create 1

uv run infinitas registry exposures create 1 \
  --audience-type public \
  --listing-mode listed \
  --install-mode enabled \
  --requested-review-mode none
```

## Review semantics

- `private` exposure: usually auto-activates
- `grant` exposure: usually auto-activates and becomes readable only through a bound grant token or explicit subject grant
- `public` exposure: opens a blocking review case and activates only after approval

## Worker semantics

The worker supports one lifecycle job kind:

- `materialize_release`

Legacy submission-oriented worker kinds are intentionally unsupported.

## Release trust and attestation

When a release flow emits provenance, `config/signing.json` controls whether SSH attestation, CI-native attestation, or both are required through `attestation.policy.release_trust_mode`.

Set `release_trust_mode` to:

- `ssh` when repository-managed SSH signing is the only required release trust signal
- `ci` when CI-native attestation is the required trust signal
- `both` when a release must satisfy both SSH provenance and CI-native attestation checks

When CI-native attestation is enabled, verify the emitted `catalog/provenance/<name>-<version>.ci.json` bundle with `python3 scripts/verify-ci-attestation.py ...` before treating the release as ready for distribution.
