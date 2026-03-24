# Command Cheat Sheet

## Local Development

```bash
pip install -r requirements.txt     # Install deps (once)
python3 run.py                      # Start dev server (auto-reload)
```

App at **http://localhost:5000** — hot-reloads on file changes.

## Docker (Production)

```bash
docker compose up --build           # Build + start
docker compose up -d                # Start detached (background)
docker compose down                 # Stop
docker compose logs -f              # Tail logs
docker compose restart              # Restart
docker compose build --no-cache     # Full rebuild (after Dockerfile changes)
```

App at **http://localhost:5000** — runs with gunicorn (2 workers).

## Useful Endpoints

```
http://localhost:5000/                      # Dashboard
http://localhost:5000/tools/<slug>          # Open a tool
http://localhost:5000/api/tools/search?q=   # Search API (JSON)
```

## Deploy (push-to-deploy via GitHub Actions)

```bash
# Day-to-day: just push to main
git add . && git commit -m "add new tool" && git push origin main
# Deploys automatically in ~90 seconds.
```

### First-Time Setup

1. **VPS**: Edit and run `deploy/setup-vps.sh` on a fresh server.
2. **GitHub Secrets** (Settings > Secrets > Actions):

   | Secret         | Value                            |
   |----------------|----------------------------------|
   | `VPS_HOST`     | Server IP address                |
   | `VPS_USER`     | SSH user (e.g. `ubuntu`)         |
   | `VPS_SSH_KEY`  | Deploy keypair private key       |

3. Push to `main` — Actions builds, pushes to GHCR, SSHs into VPS, restarts.

### Manual VPS Commands

```bash
ssh user@vps
cd ~/forge
docker compose -f docker-compose.prod.yml pull      # Pull latest image
docker compose -f docker-compose.prod.yml up -d      # Restart
docker compose -f docker-compose.prod.yml logs -f    # Tail logs
docker compose -f docker-compose.prod.yml down       # Stop
```

## Adding a Tool

```bash
cp -r app/tools/_template app/tools/my_tool   # Scaffold
# Edit files, then restart:
docker compose restart                         # Docker
# or just save (auto-reload in dev)            # Local
```
