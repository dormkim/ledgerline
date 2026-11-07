#!/usr/bin/env bash
# Check the Vultr Serverless Inference key in .env, then print the chat (text-output) model IDs to pick for LLM_MODEL.
# The models list is public (it answers without a key), so the key is checked separately with an empty request:
# a bad key gets 401/403, a good key gets a 4xx about the missing fields. No tokens are generated, so no credits are used.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=$(grep -E '^LLM_API_KEY=' .env | tail -n1 | cut -d= -f2- | tr -d '\r"'"'"' ')
[ -n "$KEY" ] || { echo "!! LLM_API_KEY is empty in $(pwd)/.env"; exit 1; }
BASE=https://api.vultrinference.com/v1

CODE=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 -X POST "$BASE/chat/completions" \
  -H "Authorization: Bearer ${KEY}" -H "Content-Type: application/json" -d '{}' || echo 000)
case "$CODE" in
  401|403) echo "!! the key was refused (HTTP $CODE): copy it again from Vultr console > Serverless Inference"; exit 1 ;;
  000)     echo "!! could not reach $BASE (network?)"; exit 1 ;;
  *)       echo ">> key accepted (empty test request answered HTTP $CODE, nothing generated)" ;;
esac

echo ">> chat models (text output) for LLM_MODEL:"
curl -fsS --max-time 20 "$BASE/models" \
  | python3 -c "
import sys, json
for m in json.load(sys.stdin).get('data', []):
    if 'text' in [o.get('type') for o in m.get('output_modalities') or []]:
        print('  ' + m['id'])
" || { echo "!! the models list failed"; exit 1; }
