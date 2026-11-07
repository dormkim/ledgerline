#!/usr/bin/env bash
# One-shot setup for a fresh Vultr Cloud Compute VM (Ubuntu 24.04, a plan WITH an IPv4 address). Run as root.
#
#   Public repo:   curl -fsSL https://raw.githubusercontent.com/<you>/<repo>/main/deploy/vultr-setup.sh | bash -s -- <repo-url>
#   Private repo or no git access: copy the folder to the VM first, then run it from there:
#                  rsync -a --exclude .env --exclude .git ./ root@<ip>:/opt/ledgerline/ && ssh root@<ip> bash /opt/ledgerline/deploy/vultr-setup.sh
#
# First run installs Docker, opens 22/80/443, creates /opt/ledgerline/.env (mode 600) and stops so you can fill it in.
# Second run (same command) builds and starts the app behind Caddy with HTTPS on <ip-with-dashes>.sslip.io.
set -euo pipefail
REPO="${1:-}"
DIR=/opt/ledgerline
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a   # no interactive "restart services?" prompt on 24.04

[ "$(id -u)" -eq 0 ] || { echo "!! run as root (sudo -i)"; exit 1; }

# A fresh VM runs unattended-upgrades for its first minutes and holds the apt lock; wait instead of failing.
APT=(apt-get -o DPkg::Lock::Timeout=600 -y)
# The lock timeout covers dpkg; "update" can still hit the lists lock, so retry it for up to ~5 minutes.
for i in $(seq 1 20); do "${APT[@]}" update && break; [ "$i" -lt 20 ] || exit 1; sleep 15; done
"${APT[@]}" install ca-certificates curl git ufw

if ! docker compose version >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

# Allow SSH before enabling the firewall so the current session is never cut off.
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
elif [ -f "$DIR/deploy/docker-compose.yml" ]; then
  echo ">> using the files already in $DIR (no git checkout)"
elif [ -n "$REPO" ]; then
  git clone "$REPO" "$DIR"
else
  echo "!! $DIR is empty: pass a repo URL, or copy the project there first (see the top of this script)"; exit 1
fi
cd "$DIR"

if [ ! -f .env ]; then
  install -m 600 .env.example .env
  echo ">> created $DIR/.env. Put LLM_API_KEY in it, run deploy/list-vultr-models.sh, set LLM_MODEL, then run this script again."
  echo "   (or set LLM_DISABLED=1 there to run with code-written text only)"
  exit 0
fi
chmod 600 .env
if ! grep -qE '^LLM_DISABLED=(1|true|yes)' .env && ! grep -qE '^LLM_MODEL=.+' .env; then
  echo "!! LLM_MODEL is empty in $DIR/.env: the app would run with template text only. Run deploy/list-vultr-models.sh and set it."
  echo "   (set LLM_DISABLED=1 if that is what you want)"; exit 1
fi

# sslip.io needs the public IPv4 (IPv6-only plans cannot get a certificate this way).
if [ -z "${PUBLIC_HOST:-}" ]; then
  # Two lookup services, so one being down does not stop the deploy.
  IP=$(curl -4 -fsS --max-time 10 https://api.ipify.org || curl -4 -fsS --max-time 10 https://ipv4.icanhazip.com || true)
  IP=$(printf '%s' "$IP" | tr -d '[:space:]')
  [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "!! no public IPv4 found; pick a Vultr plan with IPv4 or set PUBLIC_HOST"; exit 1; }
  PUBLIC_HOST="${IP//./-}.sslip.io"
fi
# Saved next to the compose file, so a later plain "docker compose up" (or a reboot) uses the same host name.
printf 'PUBLIC_HOST=%s\n' "$PUBLIC_HOST" > deploy/.env
export PUBLIC_HOST

docker compose -f deploy/docker-compose.yml up -d --build

echo ">> waiting for the app and the HTTPS certificate (first time takes up to a minute)"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 5 "https://${PUBLIC_HOST}/healthz" >/dev/null 2>&1; then
    echo ">> live at https://${PUBLIC_HOST}"
    curl -fsS "https://${PUBLIC_HOST}/healthz"; echo
    exit 0
  fi
  sleep 4
done
echo "!! https://${PUBLIC_HOST}/healthz did not answer yet. Check: docker compose -f $DIR/deploy/docker-compose.yml logs --tail 50"
exit 1
