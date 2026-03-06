# Security Notes

This is a private repository, but private does not mean secret-safe.

## Never commit

- API keys
- Access tokens
- Session cookies
- SSH private keys
- Exported auth files
- Personal datasets unless intentionally versioned

## Recommended practice

- Use environment variables for secrets.
- Keep credentials outside the repo.
- Review generated skill files before pushing.
- Redact personal or client-specific identifiers when possible.
