#!/usr/bin/env bash
# Print the model IDs your Vultr Serverless Inference key can use (pick one for LLM_MODEL). Reads the key from .env.
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=$(grep -E '^LLM_API_KEY=' .env | cut -d= -f2-)
curl -fsS https://api.vultrinference.com/v1/models -H "Authorization: Bearer ${KEY}" \
  | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin).get('data', [])]"
