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
  "credential_id": "cred_01HXYZ",
  "credential_type": "api_token",
  "principal_id": "prin_01HABC",
  "principal_kind": "user",
  "principal_slug": "alice",
  "user_id": "usr_01HDEF",
  "username": "alice",
  "scopes": ["registry:read", "registry:write"]
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
  "id": "sk_01HPQR",
  "namespace_id": "ns_01HJKL",
  "slug": "example-skill",
  "display_name": "Example Skill",
  "summary": "A demonstrative skill",
  "status": "active",
  "created_at": "2026-04-22T12:00:00Z",
  "updated_at": "2026-04-22T12:00:00Z"
}
```

`id` from this response feeds `skill_id` in step 3.

---

## Step 3: Create a Draft

Open a draft version against the skill record.

```bash
infinitas registry drafts create sk_01HPQR \
  --content-ref "skills/active/example-skill" \
  --metadata-json '{}'
```

Expected response:

```json
{
  "id": "dr_01HMNO",
  "skill_id": "sk_01HPQR",
  "state": "open",
  "content_ref": "skills/active/example-skill",
  "metadata": {},
  "created_at": "2026-04-22T12:01:00Z"
}
```

`id` from this response feeds `draft_id` in step 4.

---

## Step 4: Seal the Draft

Lock the draft and assign a semantic version.

```bash
infinitas registry drafts seal dr_01HMNO --version 0.1.0
```

Expected response:

```json
{
  "version": "0.1.0",
  "draft": {
    "state": "sealed"
  },
  "skill_version": {
    "id": "sv_01HSTU",
    "version": "0.1.0",
    "skill_id": "sk_01HPQR",
    "created_at": "2026-04-22T12:02:00Z"
  }
}
```

`skill_version.id` feeds `version_id` in step 5.

---

## Step 5: Create a Release

Initiate release materialization from a sealed version.

```bash
infinitas registry releases create sv_01HSTU
```

Expected response:

```json
{
  "id": "rl_01HVWX",
  "state": "materializing",
  "format_version": "1",
  "created_at": "2026-04-22T12:03:00Z"
}
```

Release materialization runs in the background. Poll until `state` becomes `ready`:

```bash
infinitas registry releases get rl_01HVWX
```

`id` feeds `release_id` in step 6.

---

## Step 6: Create an Exposure

Expose the release to an audience.

```bash
infinitas registry exposures create rl_01HVWX --audience-type private
```

Expected response:

```json
{
  "id": "ex_01HYZA",
  "audience_type": "private",
  "state": "active",
  "review_requirement": "none",
  "release_id": "rl_01HVWX",
  "created_at": "2026-04-22T12:04:00Z"
}
```

For public exposures, use `--audience-type public`. Public exposures require a blocking review before activation (see step 7).

`id` feeds `exposure_id` in step 7.

---

## Step 7: Review Cycle

Open a review case and record a decision. Required for `public` exposures; optional for others.

**Open a review case:**

```bash
infinitas registry reviews open-case ex_01HYZA
```

Expected response:

```json
{
  "id": "rc_01HBCD",
  "mode": "blocking",
  "state": "pending",
  "decisions": []
}
```

`id` from this response feeds `review_case_id` in the decide command.

**Record a decision:**

```bash
infinitas registry reviews decide rc_01HBCD \
  --decision approve \
  --note "LGTM"
```

Expected response:

```json
{
  "id": "rc_01HBCD",
  "mode": "blocking",
  "state": "approved",
  "decisions": [
    {
      "decision": "approve",
      "note": "LGTM",
      "reviewer_id": "usr_01HDEF",
      "decided_at": "2026-04-22T12:05:00Z"
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
