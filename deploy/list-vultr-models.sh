#!/usr/bin/env bash
# Print the model IDs your Vultr Serverless Inference key can use (pick one for LLM_MODEL). Reads the key from .env.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=$(grep -E '^LLM_API_KEY=' .env | tail -n1 | cut -d= -f2- | tr -d '\r"'"'"' ')
[ -n "$KEY" ] || { echo "!! LLM_API_KEY is empty in $(pwd)/.env"; exit 1; }
curl -fsS --max-time 20 https://api.vultrinference.com/v1/models -H "Authorization: Bearer ${KEY}" \
  | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin).get('data', [])]" \
  || { echo "!! the models list failed: check the key (Vultr console > Serverless Inference)"; exit 1; }
