---
audience: contributors, operators, automation authors
owner: repository maintainers
source_of_truth: quickstart walkthrough
last_reviewed: 2026-07-23
status: maintained
---

# Quickstart: Web Admin And Agent Workflows

This quickstart reflects the current product split:

- the web app is for human admins
- the API and CLI are for Agent publish, version, release, install, and read workflows
- the core nouns are Object, Release, Visibility, Token, Share Link, and Activity

## Prerequisites

| Variable | Default | Description |
|---|---|---|
| `INFINITAS_REGISTRY_API_BASE_URL` | `http://127.0.0.1:8000` | Hosted registry base URL |
| `INFINITAS_REGISTRY_API_TOKEN` | — | Namespace publisher Token for Agent authoring |

Issue this Token from the authenticated `/settings` page. Browser administration continues to
use Session Cookie plus CSRF and does not expose the bootstrap personal credential.

For a hosted server, complete the [Coolify deployment runbook](../ops/coolify-deployment.md)
or the [generic hosted deployment runbook](../ops/server-deployment.md) first.

## Step 1: Open the web admin console

Human admins start in the web app, not in the lifecycle internals.

Primary routes:

- `/manage` — consolidated admin console with Library, Access, Shares, and Activity sections
- `/library/{object_id}` — object detail
- `/library/{object_id}/releases/{release_id}` — release detail
- `/settings`

The consolidated `/manage` page is the entry point; removed `/access`, `/shares`, and `/activity` aliases return 404.
Use the manage console to browse Objects, inspect Releases, compare immutable versions, create or
revoke Share Links, and review Activity. There is intentionally no Web form for creating or editing
a skill; those mutations belong to the Agent/CLI surface.

## Step 2: Inspect an Object and its Releases

The v0.1 Library publishes `skill` Objects. The shared Object vocabulary is
extensible, but additional kinds are not part of the current product contract.

For each Object, the web flow should make it easy to:

- read the object summary
- inspect release history
- review the current Visibility
- see how many Tokens and Share Links exist
- open activity related to that Object

## Step 3: Issue agent access

Admins issue agent-facing Tokens from the access flow.

Minimum token types:

- `reader`
- `publisher`

Recommended usage:

- use `reader` for search, metadata reads, and install/fetch access
- use `publisher` for publishing and release creation

Issue namespace Tokens from `/settings`. A namespace publisher can create new skills and publish
only inside the issuing principal's namespace. A namespace reader is read-only and is the
recommended credential for Registry sync and long-lived install operations. Object and release
Tokens remain the narrower choice after a skill already exists.

Agents without a Token can be granted temporary Release access through a Share Link with
an expiry and optional password. Share credentials use an explicit exchange flow:

1. Create the link and retain its `resolve_url`. For a passwordless link, also retain the
   one-time `resolve_secret` returned by creation.
2. POST the password or resolve secret to `resolve_url`.
3. Read `access_token` from the successful response.
4. Send that token as a Bearer credential to the returned grant `install_url`.

The share password/secret is not accepted directly as a Bearer token.

## Step 4: Publish and version through the Agent CLI

Object creation and release production are agent-driven. The canonical publish contract is:

```text
POST /api/v1/skills
POST /api/v1/skills/{skill_id}/content
POST /api/v1/versions/{version_id}/releases
GET /api/v1/releases/{release_id}
```

Recommended flow:

1. Create the Object with `POST /api/v1/skills`.
2. Upload a `.tar.gz` content bundle with `POST /api/v1/skills/{skill_id}/content` and retain
   the returned content identifier.
3. Create an immutable version with `POST /api/v1/skills/{skill_id}/versions`, referencing that
   content identifier.
4. Create a Release with `POST /api/v1/versions/{version_id}/releases`.
5. Poll `GET /api/v1/releases/{release_id}` until the Release is ready.

For a plain Codex or OpenClaw directory containing only `SKILL.md`, the one-command Agent workflow
normalizes the source, creates the object, uploads a deterministic bundle, creates an immutable
version, waits for the Release, and creates the requested Exposure:

```bash
export INFINITAS_REGISTRY_API_BASE_URL=https://skills.infinitas.fun
export INFINITAS_REGISTRY_API_TOKEN=<namespace-publisher-token>

uv run infinitas registry publish ./example-skill \
  --version 1.0.0 \
  --visibility private
```

The command writes a 0600 publish receipt under the XDG state directory. Use `--resume` after an
interrupted upload; the receipt contains identifiers and digests, never the bearer token. A
same-version/same-digest publish is reused, while a same-version/different-digest publish is
rejected. Use `--no-wait` only when a worker will finish the Release asynchronously; it returns
`state=release-created` and does not create an Exposure until the Release is ready.

For explicit API integrations, the lower-level sequence remains:

```text
POST /api/v1/skills
POST /api/v1/skills/{skill_id}/content
POST /api/v1/skills/{skill_id}/versions
POST /api/v1/versions/{version_id}/releases
GET /api/v1/releases/{release_id}
```

Inspect and compare immutable versions with `registry versions list/get/compare`; archive is
permanent and prevents later content or version creation.

## Step 5: Read from the unified library surface

Agents and automation should consume the unified read surface:

```text
GET /api/v1/library
GET /api/v1/library/{object_id}
GET /api/v1/library/{object_id}/releases
GET /api/v1/releases/{release_id}
POST /api/v1/exposures/{exposure_id}/revoke
POST /api/v1/object-tokens/objects/{object_id}/tokens
GET /api/v1/object-tokens/objects/{object_id}/tokens
POST /api/v1/object-tokens/tokens/{token_id}/revoke
POST /api/v1/share-links/releases/{release_id}/share-links
GET /api/v1/share-links/releases/{release_id}/share-links
POST /api/v1/share-links/{share_id}/resolve
POST /api/v1/share-links/{share_id}/revoke
GET /api/v1/activity
```

This keeps read and governance actions centered on Objects and Releases instead of lifecycle internals.

## Step 6: Share and install in a clean Agent directory

Create a Share Link from the CLI or Web release page. Passwords are read from an environment
variable and are never included in generated commands or receipts:

```bash
export INFINITAS_SHARE_PASSWORD='<share-password>'
uv run infinitas registry shares create <release_id> --name agent-demo --password-env INFINITAS_SHARE_PASSWORD
uv run infinitas install from-share '<resolve-url>' ~/.openclaw/skills
```

For a passwordless share, use `INFINITAS_SHARE_SECRET` when the one-time resolve secret is
returned. The installer verifies manifest, bundle, provenance, and signature before writing the
target. Revoked or expired shares return a clear failure.

## Step 7: Configure a long-lived Hosted Registry and rollback

Share Links are for temporary distribution. Configure a read-token-backed HTTP source for repeat
install, switch, and rollback operations:

```bash
export INFINITAS_REGISTRY_READ_TOKEN='<namespace-reader-token>'
uv run infinitas registry bootstrap hosted \
  https://skills.infinitas.fun/api/v1/registry \
  --repo-root . --token-env INFINITAS_REGISTRY_READ_TOKEN --set-default --json
uv run infinitas registry sources --repo-root . sync hosted --json
uv run infinitas install exact <publisher>/<skill> ~/.openclaw/skills --version 1.0.0 --registry hosted --json
uv run infinitas install switch <publisher>/<skill> ~/.openclaw/skills --to-version 1.1.0 --registry hosted --json
uv run infinitas install rollback <publisher>/<skill> ~/.openclaw/skills --json
```

Bootstrap also installs the Registry's public signing trust root and integrity policy. The config
stores only the environment variable name. Never persist a Share token for rollback.

## Step 8: Build the new frontend with `kimi cli`

All net-new frontend layout and interaction work for the admin cutover must be generated and iterated with `kimi cli`.

Hand edits should be limited to:

- FastAPI route wiring
- template integration glue
- bug fixes
- focused accessibility and performance follow-up work

## See also

- [Web admin and agent product contract](../specs/web-admin-agent-product-contract.md)
- [Registry CLI reference](../reference/registry-cli.md)
- [Error catalog](../reference/error-catalog.md)
- [CLI reference](../reference/cli-reference.md)
- [Coolify deployment](../ops/coolify-deployment.md)
