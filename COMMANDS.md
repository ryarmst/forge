# Command Cheat Sheet

## Local Development

```bash
pip install -r requirements.txt     # Install deps (once)
python3 run.py                      # Start dev server (auto-reload)
```

App at **http://localhost:5000** — hot-reloads on file changes.

## Deploy

```bash
git add . && git commit -m "update" && git push origin main
# GitHub Actions builds, pushes to GHCR, deploys to VPS. ~90 seconds.
```

Watch runs at: https://github.com/ryarmst/forge/actions

## VPS Management

```bash
ssh root@<VPS_IP>
cd ~/forge
docker compose -f docker-compose.prod.yml pull        # Pull latest image
docker compose -f docker-compose.prod.yml up -d        # Start/restart
docker compose -f docker-compose.prod.yml logs -f      # Tail logs
docker compose -f docker-compose.prod.yml down         # Stop
docker compose -f docker-compose.prod.yml restart caddy # Restart Caddy only
```

## mTLS Certificate Management

Run locally from `deploy/mtls/`:

```bash
# Create the CA (one-time)
./init-ca.sh

# Create a client cert for a user
./create-client-cert.sh alice

# Copy CA to VPS (after init or regeneration)
scp ca/ca.crt root@<VPS_IP>:~/forge/certs/

# Restart Caddy on VPS after cert changes
ssh root@<VPS_IP> "cd ~/forge && docker compose -f docker-compose.prod.yml restart caddy"
```

Output files:
- `ca/ca.crt` + `ca.key` — root CA (keep `ca.key` secret)
- `clients/<user>.p12` — send this to the user to import into their browser

## GitHub Secrets

Set at `Settings > Secrets and variables > Actions`:

| Secret | Value |
|--------|-------|
| `VPS_HOST` | Server IP address |
| `VPS_USER` | `root` |
| `VPS_SSH_KEY` | Deploy keypair private key |

## Adding a Tool

```bash
cp -r app/tools/_template app/tools/my_tool
# Edit __init__.py — set slug to "my_tool", fill all fields
# Edit tool.html — build your UI
# Push to deploy
```

## Docker (Local, without VPS)

```bash
docker compose up --build           # Build + start
docker compose up -d                # Start detached
docker compose down                 # Stop
docker compose logs -f              # Tail logs
docker compose build --no-cache     # Full rebuild
```
