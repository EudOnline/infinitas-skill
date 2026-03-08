#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print('usage: scripts/verify-provenance.py <provenance-json>', file=sys.stderr)
    raise SystemExit(1)

path = Path(sys.argv[1]).resolve()
sig_path = path.with_suffix(path.suffix + '.sig.json')
if not sig_path.exists():
    print(f'missing signature file: {sig_path}', file=sys.stderr)
    raise SystemExit(1)
key = os.environ.get('INFINITAS_SKILL_SIGNING_KEY')
if not key:
    print('INFINITAS_SKILL_SIGNING_KEY is required', file=sys.stderr)
    raise SystemExit(1)
sig = json.loads(sig_path.read_text(encoding='utf-8'))
payload = path.read_bytes()
digest = hashlib.sha256(payload).hexdigest()
if digest != sig.get('sha256'):
    print('FAIL: sha256 mismatch', file=sys.stderr)
    raise SystemExit(1)
expected = hmac.new(key.encode('utf-8'), payload, hashlib.sha256).digest()
actual = base64.b64decode(sig['signature_b64'])
if not hmac.compare_digest(expected, actual):
    print('FAIL: signature mismatch', file=sys.stderr)
    raise SystemExit(1)
print(f'OK: verified {path.name} with key_id={sig.get("key_id")}')
