---
audience: contributors, integrators, operators
owner: repository maintainers
source_of_truth: legacy ai protocol annex
last_reviewed: 2026-04-21
status: legacy
---

# Hosted Registry Protocol

## Purpose

This document defines the machine-facing contract for consuming a hosted `infinitas-skill` registry over HTTPS instead of through a local Git checkout.

Use this protocol when:

- an operator exposes generated catalogs and immutable bundles from a server
- clients should install skills without cloning the whole repository
- automation needs a stable remote registry surface

## Core model

A hosted registry is still **immutable-artifact-first**.

That means clients must resolve and install from:

- hosted catalog views
- hosted distribution manifests
- hosted release bundles
- hosted provenance / signatures

Clients must not treat the hosted registry as permission to install mutable source directories.

## Required endpoints

Unless explicitly overridden in registry config, a hosted registry should expose:

- `/ai-index.json`
- `/distributions.json`
- `/compatibility.json`
- `/skills/<publisher>/<skill>/<version>/manifest.json`
- `/skills/<publisher>/<skill>/<version>/skill.tar.gz`
- `/provenance/<skill>-<version>.json`
- `/provenance/<skill>-<version>.json.ssig`

These endpoints may be served directly or mapped from the repository’s generated `catalog/` outputs.

## Built-in hosted app surface

The built-in `server.app` serves this protocol from the hosted artifact root under:

- `/registry/ai-index.json`
- `/registry/distributions.json`
- `/registry/compatibility.json`
- `/registry/discovery-index.json`
- `/registry/skills/<publisher>/<skill>/<version>/manifest.json`
- `/registry/skills/<publisher>/<skill>/<version>/skill.tar.gz`
- `/registry/provenance/<skill>-<version>.json`
- `/registry/provenance/<skill>-<version>.json.ssig`

For compatibility with existing generated manifests, the built-in app also serves legacy catalog-backed refs such as:

- `/registry/catalog/distributions/<publisher>/<skill>/<version>/manifest.json`
- `/registry/catalog/distributions/<publisher>/<skill>/<version>/skill.tar.gz`
- `/registry/catalog/provenance/<skill>-<version>.json`

When you use the built-in hosted app, set the registry `base_url` to the `/registry` prefix itself, for example:

```json
{
  "name": "hosted",
  "kind": "http",
  "base_url": "https://skills.example.com/registry"
}
```

This surface remains read-only and immutable-artifact-first. Publish jobs still generate artifacts on disk first, then the hosted app serves that synchronized artifact root.

## Registry source config

Hosted registries are declared in `config/registry-sources.json` like this:

```json
{
  "name": "hosted",
  "kind": "http",
  "base_url": "https://skills.example.com/registry",
  "enabled": true,
  "priority": 100,
  "trust": "private",
  "auth": {
    "mode": "token",
    "env": "INFINITAS_REGISTRY_TOKEN"
  }
}
```

## Auth

Supported auth modes:

- `none`
- `token`

When `auth.mode` is `token`, clients should send:

```text
Authorization: Bearer <value-of-auth.env>
```

For the built-in hosted app, registry-read protection is configured separately from hosted API users:

- `INFINITAS_REGISTRY_READ_TOKENS` — JSON array of raw bearer tokens allowed to read `/registry/*`
- unset or empty means `/registry/*` stays public for local/dev compatibility
- the control-plane API under `/api/v1/*` still uses hosted user tokens from `INFINITAS_SERVER_BOOTSTRAP_USERS`

## Hard rules

- `private`, `trusted`, and `public` hosted registries must use HTTPS
- hosted install remains immutable-only
- provenance and manifest verification still apply
- hosted distribution is a transport change, not a trust-model downgrade

## Relationship to existing AI contracts

Hosted registry use does not replace:

- `docs/ai/discovery.md`
- `docs/ai/pull.md`
- `docs/ai/publish.md`

Instead, it gives those contracts a remote transport for catalog and artifact resolution.
