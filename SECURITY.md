# Security Policy

## Supported versions

Before 1.0, only the latest tagged release and the current `main` branch receive security fixes.
Older snapshots are unsupported. Operators should upgrade rather than backport fixes locally.

## Reporting a vulnerability

Do not open a public issue or include exploit details in normal project chat.

1. Prefer GitHub private vulnerability reporting or a private Security Advisory for this repository.
2. If that feature is unavailable, contact the repository administrator through the existing
   private organizational channel and label the message `infinitas-skill security`.
3. Include affected version/commit, deployment shape, reproduction steps, impact, and any known
   workaround. Remove live credentials and personal data from evidence.

The response targets are acknowledgement within 3 business days, initial severity assessment
within 7 business days, and a remediation plan for confirmed high or critical issues within
14 business days. Complex fixes may take longer; maintainers should keep the reporter updated.

## Coordinated disclosure

Allow maintainers time to reproduce, patch, test, rotate affected credentials, and prepare an
advisory before public disclosure. Credit is offered when requested and legally appropriate.

## Deployment threat boundary

The supported v0.1 Hosted profile is a trusted, single-node deployment using durable SQLite and
filesystem-backed artifacts. It does not claim hostile multi-tenant isolation, horizontal API or
worker scaling, or production PostgreSQL support. TLS termination, host hardening, backups,
filesystem permissions, outbound network policy, and access to signing keys remain operator
responsibilities.

Browser administrator passwords, Agent tokens, registry read tokens, session cookies, share
secrets, and SSH signing keys are separate credentials. Do not reuse them. A suspected exposure
requires rotation or revocation of every affected credential, invalidation of active sessions and
Share Links where applicable, and review of Activity/audit records.

## Repository and dependency hygiene

Never commit API keys, tokens, cookies, SSH private keys, auth exports, or unintended personal
datasets. Keep secrets in environment or secret-management systems, review generated bundles for
embedded credentials, and run the repository dependency and release gates before publishing.

Security fixes should include regression tests when safe. Third-party vulnerabilities are triaged
by reachability, exploitability, and deployment exposure; a clean scanner result does not replace
product-level threat analysis.
