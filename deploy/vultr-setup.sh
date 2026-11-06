#!/usr/bin/env bash
# One-shot setup for a fresh Vultr Cloud Compute VM (Ubuntu 24.04). Run as root:
#   curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy/vultr-setup.sh | bash -s -- <repo-url>
# Then put the LLM settings in /opt/ledgerline/.env and re-run the last line.
set -euo pipefail
REPO="${1:?usage: vultr-setup.sh <git repo url>}"

apt-get update -y && apt-get install -y ca-certificates curl git ufw
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh

ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

[ -d /opt/ledgerline ] || git clone "$REPO" /opt/ledgerline
cd /opt/ledgerline && git pull --ff-only
[ -f .env ] || { cp .env.example .env; chmod 600 .env; echo ">> edit /opt/ledgerline/.env (LLM_API_KEY, LLM_MODEL), then re-run this script"; }

IP=$(curl -fsS https://api.ipify.org)
export PUBLIC_HOST="${PUBLIC_HOST:-${IP//./-}.sslip.io}"
docker compose -f deploy/docker-compose.yml up -d --build
echo ">> live at https://${PUBLIC_HOST}  (health: https://${PUBLIC_HOST}/healthz)"
