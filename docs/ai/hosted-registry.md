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
