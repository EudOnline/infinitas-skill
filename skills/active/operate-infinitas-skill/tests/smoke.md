# Smoke test

Scenario:

The user says: "Create a new private skill entry, author it as a draft, turn it into a release, expose it publicly after review, then tell another agent which hosted endpoints to use."

Expected behavior:

- identify the private-first lifecycle stages before choosing commands
- use `scripts/registryctl.py` or hosted API endpoints instead of removed publish/promotion scripts
- require public exposure review before calling the release public
- point the second agent at `/api/v1/install/*` or `/registry/*`, not source folders
