# Forge

A modular security testing tools platform. Flask backend, vanilla JS frontend, dark terminal aesthetic.

## Quick Start (Local Dev)

```bash
pip install -r requirements.txt
python3 run.py                    # http://localhost:5000
```

## Production Deployment

Forge deploys automatically via GitHub Actions on push to `main`. The pipeline builds a Docker image, pushes it to GHCR, then SSHs into the VPS to pull and restart.

### Prerequisites

- A VPS running Ubuntu with Docker installed
- A domain pointed at the VPS (A record)
- SSH key access to the VPS

### VPS Setup (one-time)

```bash
# 1. SSH in
ssh root@<VPS_IP>

# 2. Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# 3. Create project directory and compose file
mkdir -p ~/forge/certs
cat > ~/forge/docker-compose.prod.yml <<'EOF'
services:
  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./certs:/etc/caddy/certs:ro
      - caddy_data:/data
    depends_on:
      - forge
    restart: unless-stopped
  forge:
    image: ghcr.io/ryarmst/forge:latest
    expose:
      - "5000"
    restart: unless-stopped
    environment:
      - FLASK_ENV=production
volumes:
  caddy_data:
EOF

# 4. Open firewall
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp
ufw --force enable
```

### GitHub Secrets

Add these at `Settings > Secrets and variables > Actions`:

| Secret | Value |
|--------|-------|
| `VPS_HOST` | Server IP address |
| `VPS_USER` | `root` |
| `VPS_SSH_KEY` | Private SSH key for the VPS |

### mTLS (Client Certificates)

Access requires a client certificate. Caddy terminates TLS and enforces mTLS — connections without a valid cert are refused.

**Generate the CA (one-time, run locally):**

```bash
cd deploy/mtls
./init-ca.sh
```

**Create a client certificate for a user:**

```bash
./create-client-cert.sh <username>
```

This produces `clients/<username>.p12` — a PKCS12 bundle the user imports into their browser.

**Copy the CA cert to the VPS:**

```bash
scp ca/ca.crt root@<VPS_IP>:~/forge/certs/
```

**User setup:**

1. Import the `.p12` file into their browser (Settings > Certificates > Your Certificates)
2. Access `https://westminsteroffensive.ca`
3. Browser prompts to select the client cert — done

**To grant a new user access:** Run `create-client-cert.sh` with their name, send them the `.p12` file.

**To revoke access:** Regenerate the CA (`rm -rf ca/ && ./init-ca.sh`), reissue certs for active users only, replace `ca.crt` on the VPS, restart Caddy.

### Deploy

```bash
git add . && git commit -m "update" && git push origin main
# Automatic. Live in ~90 seconds.
```

## Adding a Tool

```bash
cp -r app/tools/_template app/tools/my_tool
# Edit __init__.py (slug must match dir name)
# Edit tool.html (build your UI)
# Push to deploy
```

See `NEW_TOOL_GUIDE.md` for full requirements, or `TOOL_GENERATION_PROMPT.md` for LLM-assisted tool creation.

## Routes

| Route | Purpose |
|---|---|
| `GET /` | Dashboard with live search |
| `GET /tools/<slug>` | Individual tool page |
| `GET /api/tools/search?q=` | JSON search (programmatic use) |

## Project Structure

```
forge/
├── app/
│   ├── __init__.py          # App factory, tool auto-registration
│   ├── routes.py            # Dashboard, tool pages, search API
│   ├── tool_registry.py     # Auto-discovers tools at startup
│   ├── static/              # CSS + JS (no frameworks)
│   ├── templates/           # Jinja2 (base, index, tool_base, 404)
│   ├── tools/               # Drop-in tool modules (auto-discovered)
│   └── utils/               # Shared helpers (subprocess streaming)
├── deploy/
│   ├── Caddyfile            # Caddy reverse proxy + mTLS config
│   ├── setup-vps.sh         # VPS bootstrap script
│   └── mtls/                # CA and cert generation scripts
├── .github/workflows/       # CI/CD pipeline
├── Dockerfile               # python:3.12-slim + gunicorn
├── docker-compose.yml       # Local dev
└── docker-compose.prod.yml  # Production (Caddy + Forge)
```
