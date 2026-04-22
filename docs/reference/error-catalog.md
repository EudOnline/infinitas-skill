---
audience: operators, automation authors
owner: repository maintainers
source_of_truth: error catalog
last_reviewed: 2026-04-22
status: maintained
---

# Error Catalog

Common error patterns, exit codes, HTTP status codes, and remediation for `infinitas` CLI and hosted registry operations.

## CLI exit codes

| Code | Meaning | Cause |
|------|---------|-------|
| 0 | Success | Command completed normally |
| 1 | Failure | Application error, API error, validation failure, or `fail()` call |
| 2 | Usage error | argparse could not parse the provided arguments |

## Hosted registry API errors

These are returned as HTTP status codes in API responses. The CLI surface converts them to stderr text and exit code 1.

### Authentication (401)

| Error detail | Cause | Remediation |
|---|---|---|
| `missing bearer token` | No `Authorization` header or cookie | Provide `--token` flag or set `INFINITAS_REGISTRY_API_TOKEN` |
| `invalid bearer token` | Token does not match any active credential | Verify token value; check for typos or revoked tokens |
| `search requires authentication` | Search endpoint accessed without credentials for a non-public registry | Provide authentication credentials |

### Authorization (403)

| Error detail | Cause | Remediation |
|---|---|---|
| `authoring principal required` | Credential does not resolve to a principal | Use a `personal_token` credential type, not a bare grant token |
| `insufficient scope` | Principal lacks required scope (`api:user`, `authoring:write`, `skill:write`, etc.) | Use a credential with the required scope |
| `skill namespace access denied` | Principal does not own the target namespace and is not a maintainer | Use a principal that owns the namespace, or escalate to a maintainer |
| `release namespace access denied` | Principal does not own the release's namespace | Same as above |
| `insufficient role` | User role does not meet the required threshold | Operation requires `maintainer` role |
| `user session required` | Catalog or install endpoint requires a user session, not a grant credential | Use a personal token instead |
| `grant credential required` | Grant-specific endpoint received a non-grant credential | Use a grant token |
| `release access denied` | Principal does not have access to the release via any active exposure | Check exposure audience_type and grant state |

### Not found (404)

| Error detail | Cause | Remediation |
|---|---|---|
| `skill not found` | Skill ID does not exist | Verify the skill ID from `registry skills get` or the UI |
| `draft not found` | Draft ID does not exist | Verify the draft ID from the create response |
| `skill version not found` | Version ID does not exist | Verify the version ID from the seal response |
| `release not found` | Release ID does not exist | Verify the release ID from the create response |
| `exposure not found` | Exposure ID does not exist | Verify the exposure ID from the create response |
| `review case not found` | Review case ID does not exist | Verify the case ID from the open-case response |
| `artifact not found` | Requested artifact path does not map to a stored file | Check release artifact list via `releases artifacts` |
| `install target not found` | Target directory for install resolution does not exist | Create the target directory first |
| `uploaded content artifact not found` | Referenced upload artifact does not exist | Re-upload the artifact |

### Conflict (409)

| Error detail | Cause | Remediation |
|---|---|---|
| `skill slug already exists in namespace` | A skill with the same slug already exists in the principal's namespace | Choose a different slug or use the existing skill |
| `sealed draft is immutable` | Attempted to update a draft that is already sealed | Create a new draft instead |
| `draft is already sealed` | Attempted to seal a draft that was already sealed | Use the existing sealed version |
| `skill version already exists` | A version with the same semver string already exists for this skill | Use a different version string |
| `release already exists for skill version` | A release already exists for this version | Use `releases get` to fetch the existing release |
| `only ready releases can be exposed` | Release materialization has not completed | Poll `releases get` until `state` becomes `ready` |
| `draft content_ref must be an immutable snapshot before sealing` | Content ref is not a valid immutable snapshot | Ensure content is uploaded or referenced as an immutable artifact |
| `review case is already closed` | Attempted to record a decision on a closed case | Open a new review case |
| `closed exposure cannot be patched` | Attempted to update an ended/revoked exposure | Create a new exposure |
| `closed exposure cannot be re-activated` | Attempted to activate a revoked exposure | Create a new exposure |
| `blocking review must be resolved before activation` | Public exposure requires blocking review to pass | Record a review decision first |
| `blocking review must be approved before activation` | Blocking review received a rejection | Re-open the review or create a new exposure |
| `ambiguous short skill ref` | Multiple skills match a partial reference | Use the full qualified name |

## Registry CLI specific errors

These originate from `src/infinitas_skill/registry/cli.py` and exit with code 1.

| Error message | Cause | Remediation |
|---|---|---|
| `API request failed: <exc>` | Network error connecting to the registry | Check `--base-url`, network connectivity, and server status |
| `<response.text>` | Server returned HTTP 400+ | Parse the response body for the specific error detail |
| `invalid --metadata-json: <exc>` | `--metadata-json` value is not valid JSON | Ensure the value is a valid JSON string |
| `invalid --metadata-json: expected JSON object` | `--metadata-json` parsed as JSON but is not an object | Wrap the value in `{}` |
| `drafts update requires at least one of --content-ref or --metadata-json` | Neither flag provided to `drafts update` | Provide at least one of the flags |
| `exposures update requires at least one of --listing-mode, --install-mode, or --requested-review-mode` | Neither flag provided to `exposures update` | Provide at least one of the flags |
| `grant listing API is not available yet` | `grants list` is a stub command | Track the grants feature milestone |
| `grant token issuing API is not available yet` | `grants create-token` is a stub command | Track the grants feature milestone |
| `grant revoke API is not available yet` | `grants revoke` is a stub command | Track the grants feature milestone |

## Local CLI errors

### Install and integrity

| Error pattern | Source | Cause | Remediation |
|---|---|---|---|
| `install manifest must be a JSON object` | `install_manifest.py` | Corrupted manifest file | Delete the manifest and reinstall |
| `unsupported schema_version` | `install_manifest.py` | Manifest version does not match | Upgrade the CLI or recreate the manifest |
| `missing manifest: <path>` | `install_manifest.py` | No install manifest in target directory | Run an install command first |
| `invalid install manifest JSON: <exc>` | `install_manifest.py` | Manifest file contains invalid JSON | Delete and reinstall |
| `install manifest skills must be an object` | `install_manifest.py` | `skills` field is not a dict | Delete and reinstall |
| `install manifest history must be an object` | `install_manifest.py` | `history` field is not a dict | Delete and reinstall |
| `installed skill not found: <name>` | `installed_skill.py` | Requested skill name does not exist in manifest | Check installed skills list |
| `unknown reviewer: <name>` | `reviews.py` | Reviewer not in configured reviewers list | Check `policy/promotion-policy.json` reviewer groups |
| `invalid decision: <value>` | `reviews.py` | Decision is not `approved` or `rejected` | Use one of the allowed values |

### Release and attestation

| Error pattern | Source | Cause | Remediation |
|---|---|---|---|
| `missing SSH attestation signature` | `attestation.py` | No `.ssig` file alongside provenance | Re-run release attestation with SSH signing |
| `SSH attestation verification failed` | `attestation.py` | Signature does not validate against `config/allowed_signers` | Check signer identity and key |
| `cannot derive SSH companion path` | `attestation.py` | Provenance path does not follow expected naming | Ensure provenance follows `<skill>-<version>.json` naming |
| `required transparency log proof is missing or unverified` | `attestation.py` | Transparency log submission expected but absent | Submit transparency log entry or adjust policy |
| `ci.<field> does not match repo-managed` | `attestation.py` | CI attestation fields diverge from repo config | Ensure CI workflow uses correct repo/workflow values |

### Policy

| Error pattern | Source | Cause | Remediation |
|---|---|---|---|
| `ReviewPolicyError` | `reviews.py`, `policy/service.py` | Policy evaluation failed (quorum, group, or stage errors) | Check promotion policy groups and quorum settings |
| `invalid JSON in <path>` | `policy/service.py` | Policy file contains invalid JSON | Fix the JSON syntax |
| `<path> must contain a JSON object` | `policy/service.py` | Policy file is not a JSON object | Wrap content in `{}` |
| `missing AI index: <path>` | `discovery/resolver.py` | No `ai-index.json` in catalog directory | Run `scripts/build-catalog.sh` |
| `could not resolve skill <name>` | `discovery/inspect.py` | Skill name not found in any registry | Check skill name or rebuild catalog |

## See also

- [Registry CLI reference](registry-cli.md)
- [Quickstart](../guide/quickstart.md)
- [Installed skill integrity](installed-skill-integrity.md)
- [Release attestation](release-attestation.md)
- [Promotion policy](promotion-policy.md)
