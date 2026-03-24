#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Forge VPS Bootstrap — run once on a fresh Ubuntu/Debian VPS.
#
#   curl -sSL <raw-github-url>/deploy/setup-vps.sh | bash
#   — or —
#   scp deploy/setup-vps.sh user@vps:~ && ssh user@vps 'bash setup-vps.sh'
#
# Prerequisites: root or sudo access, internet connectivity.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

GHCR_USER=""    # ← your GitHub username (lowercase)
GHCR_TOKEN=""   # ← GitHub PAT with read:packages scope
IMAGE=""        # ← e.g. ghcr.io/yourname/forge:latest

# ── Validation ──────────────────────────────────────────────
if [[ -z "$GHCR_USER" || -z "$GHCR_TOKEN" || -z "$IMAGE" ]]; then
  echo "ERROR: Edit this script and fill in GHCR_USER, GHCR_TOKEN, and IMAGE."
  exit 1
fi

echo "==> Installing Docker..."
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo systemctl enable --now docker
  sudo usermod -aG docker "$USER"
  echo "    Docker installed. You may need to re-login for group changes."
else
  echo "    Docker already installed, skipping."
fi

echo "==> Installing Docker Compose plugin..."
if ! docker compose version &>/dev/null; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-compose-plugin
else
  echo "    Docker Compose already available, skipping."
fi

echo "==> Authenticating to GHCR..."
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin

echo "==> Setting up project directory..."
mkdir -p ~/forge
cat > ~/forge/docker-compose.prod.yml <<EOF
services:
  forge:
    image: ${IMAGE}
    ports:
      - "5000:5000"
    restart: unless-stopped
    environment:
      - FLASK_ENV=production
EOF

echo "==> Pulling image and starting container..."
cd ~/forge
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

echo "==> Configuring firewall (UFW)..."
if command -v ufw &>/dev/null; then
  sudo ufw allow 22/tcp   # SSH
  sudo ufw allow 80/tcp   # HTTP
  sudo ufw allow 443/tcp  # HTTPS
  sudo ufw allow 5000/tcp # Forge (direct access, remove after setting up reverse proxy)
  sudo ufw --force enable
  echo "    UFW enabled."
else
  echo "    UFW not found, skipping firewall setup."
fi

cat <<'DONE'

════════════════════════════════════════════════
  Forge is running at http://<your-vps-ip>:5000

  Optional: set up Caddy for automatic HTTPS:

    sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
      | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
      | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt update && sudo apt install -y caddy

    # Then create /etc/caddy/Caddyfile:
    #   yourdomain.com {
    #       reverse_proxy localhost:5000
    #   }
    # sudo systemctl reload caddy
════════════════════════════════════════════════
DONE
