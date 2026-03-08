#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print('usage: scripts/sign-provenance.py <provenance-json>', file=sys.stderr)
    raise SystemExit(1)

path = Path(sys.argv[1]).resolve()
key = os.environ.get('INFINITAS_SKILL_SIGNING_KEY')
if not key:
    print('INFINITAS_SKILL_SIGNING_KEY is required', file=sys.stderr)
    raise SystemExit(1)
key_id = os.environ.get('INFINITAS_SKILL_SIGNING_KEY_ID', 'default')
payload = path.read_bytes()
digest = hashlib.sha256(payload).hexdigest()
signature = hmac.new(key.encode('utf-8'), payload, hashlib.sha256).digest()
out = {
    'file': path.name,
    'sha256': digest,
    'algorithm': 'hmac-sha256',
    'key_id': key_id,
    'signature_b64': base64.b64encode(signature).decode('ascii'),
}
out_path = path.with_suffix(path.suffix + '.sig.json')
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(out_path)
