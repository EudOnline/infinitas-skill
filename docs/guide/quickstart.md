---
audience: contributors, automation authors
owner: repository maintainers
source_of_truth: quickstart walkthrough
last_reviewed: 2026-04-22
status: maintained
---

# Quickstart: Publish and Install a Skill

## Prerequisites

| Variable | Default | Description |
|---|---|---|
| `INFINITAS_REGISTRY_API_BASE_URL` | `http://127.0.0.1:8000` | Registry API root |
| `INFINITAS_REGISTRY_API_TOKEN` | — | Bearer token from bootstrap or operator |

All commands accept `--base-url` and `--token` flags as alternatives to environment variables.

The registry server must be running and accessible before proceeding.

---

## Step 1: Verify Authentication

Confirm that your token is valid and inspect the associated principal.

```bash
infinitas registry tokens me --token <YOUR_TOKEN>
```

Expected response:

```json
{
  "credential_id": 1,
  "credential_type": "personal_token",
  "principal_id": 1,
  "principal_kind": "user",
  "principal_slug": "maintainer",
  "user_id": 1,
  "username": "maintainer",
  "scopes": ["session:user", "api:user"]
}
```

`principal_id` and `username` are used in subsequent steps for ownership and audit trails.

---

## Step 2: Create a Skill Record

Register a new skill slug on the registry.

```bash
infinitas registry skills create \
  --slug example-skill \
  --display-name "Example Skill" \
  --summary "A demonstrative skill"
```

Expected response:

```json
{
  "id": 1,
  "namespace_id": 1,
  "slug": "example-skill",
  "display_name": "Example Skill",
  "summary": "A demonstrative skill",
  "status": "active",
  "default_visibility_profile": null,
  "created_by_principal_id": 1,
  "created_at": "2026-04-22T10:00:00Z",
  "updated_at": "2026-04-22T10:00:00Z"
}
```

`id` from this response feeds `skill_id` in step 3.

---

## Step 3: Create a Draft

Open a draft version against the skill record.

```bash
infinitas registry drafts create 1 \
  --content-ref "skills/active/example-skill" \
  --metadata-json '{}'
```

Expected response:

```json
{
  "id": 1,
  "skill_id": 1,
  "base_version_id": null,
  "state": "open",
  "content_mode": "external_ref",
  "content_ref": "skills/active/example-skill",
  "content_artifact_id": null,
  "metadata": {},
  "updated_by_principal_id": 1,
  "updated_at": "2026-04-22T10:01:00Z"
}
```

`id` from this response feeds `draft_id` in step 4.

---

## Step 4: Seal the Draft

Lock the draft and assign a semantic version.

```bash
infinitas registry drafts seal 1 --version 0.1.0
```

Expected response:

```json
{
  "version": "0.1.0",
  "draft": {
    "id": 1,
    "skill_id": 1,
    "base_version_id": null,
    "state": "sealed",
    "content_mode": "external_ref",
    "content_ref": "skills/active/example-skill",
    "content_artifact_id": null,
    "metadata": {},
    "updated_by_principal_id": 1,
    "updated_at": "2026-04-22T10:02:00Z"
  },
  "skill_version": {
    "id": 1,
    "skill_id": 1,
    "version": "0.1.0",
    "content_digest": "sha256:abc123...",
    "metadata_digest": "sha256:def456...",
    "sealed_manifest_json": "{\"name\":\"example-skill\"}",
    "sealed_manifest": {"name": "example-skill"},
    "created_from_draft_id": 1,
    "created_by_principal_id": 1,
    "created_at": "2026-04-22T10:02:00Z"
  }
}
```

`skill_version.id` feeds `version_id` in step 5.

---

## Step 5: Create a Release

Initiate release materialization from a sealed version.

```bash
infinitas registry releases create 1
```

Expected response:

```json
{
  "id": 1,
  "skill_version_id": 1,
  "state": "pending",
  "format_version": "v1",
  "manifest_artifact_id": null,
  "bundle_artifact_id": null,
  "signature_artifact_id": null,
  "provenance_artifact_id": null,
  "created_by_principal_id": 1,
  "created_at": "2026-04-22T10:03:00Z",
  "ready_at": null,
  "platform_compatibility": {}
}
```

Release materialization runs in the background. Poll until `state` becomes `ready`:

```bash
infinitas registry releases get 1
```

`id` feeds `release_id` in step 6.

---

## Step 6: Create an Exposure

Expose the release to an audience.

```bash
infinitas registry exposures create 1 --audience-type private
```

Expected response:

```json
{
  "id": 1,
  "release_id": 1,
  "audience_type": "private",
  "listing_mode": "listed",
  "install_mode": "enabled",
  "review_requirement": "none",
  "requested_review_mode": "none",
  "state": "active",
  "requested_by_principal_id": 1,
  "policy_snapshot": {},
  "activated_at": "2026-04-22T10:04:00Z",
  "ended_at": null
}
```

For public exposures, use `--audience-type public`. Public exposures require a blocking review before activation (see step 7).

`id` feeds `exposure_id` in step 7.

---

## Step 7: Review Cycle

Open a review case and record a decision. Required for `public` exposures; optional for others.

**Open a review case:**

```bash
infinitas registry reviews open-case 1
```

Expected response:

```json
{
  "id": 1,
  "exposure_id": 1,
  "policy_id": 1,
  "mode": "blocking",
  "state": "open",
  "opened_by_principal_id": 1,
  "opened_at": "2026-04-22T10:05:00Z",
  "closed_at": null,
  "decisions": []
}
```

`id` from this response feeds `review_case_id` in the decide command.

**Record a decision:**

```bash
infinitas registry reviews decide 1 \
  --decision approve \
  --note "LGTM"
```

Expected response:

```json
{
  "id": 1,
  "exposure_id": 1,
  "policy_id": 1,
  "mode": "blocking",
  "state": "approved",
  "opened_by_principal_id": 1,
  "opened_at": "2026-04-22T10:05:00Z",
  "closed_at": "2026-04-22T10:06:00Z",
  "decisions": [
    {
      "id": 1,
      "review_case_id": 1,
      "reviewer_principal_id": 2,
      "decision": "approve",
      "note": "LGTM",
      "evidence": {},
      "created_at": "2026-04-22T10:06:00Z"
    }
  ]
}
```

For public exposures, approval auto-activates the exposure.

---

## Step 8: Discover and Install

Search the registry and install the skill to a local directory.

**Search:**

```bash
infinitas discovery search example-skill --json
```

**Install:**

```bash
infinitas install by-name example-skill --target-dir .installed-skills
```

---

## Audience Types Reference

| `audience_type` | `review_required` | `auto_activate` | Access |
|---|---|---|---|
| `private` | none | yes | requesting principal only |
| `grant` | optional | yes (if not blocking) | principals with active AccessGrant |
| `authenticated` | none | yes | any logged-in user |
| `public` | blocking | no | anyone |

---

## See Also

- [Registry CLI reference](../reference/registry-cli.md)
- [CLI reference](../reference/cli-reference.md)
- [Release checklist](../ops/release-checklist.md)
- [Signing bootstrap](../ops/signing-bootstrap.md)
- [Repository conventions](conventions.md)
