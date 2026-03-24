# Forge

A modular security testing tools platform. Flask backend, vanilla JS frontend, dark terminal aesthetic.

## Quick Start

```bash
# Dev (local)
pip install -r requirements.txt
python3 run.py                    # http://localhost:5000

# Production (Docker)
docker compose up --build         # http://localhost:5000
```

## Structure

```
forge/
├── app/
│   ├── __init__.py          # App factory, tool auto-registration
│   ├── routes.py            # Dashboard, tool pages, search API
│   ├── tool_registry.py     # Auto-discovers tools at startup
│   ├── static/              # CSS + JS (no frameworks)
│   ├── templates/           # Jinja2 (base, index, tool_base, 404)
│   ├── tools/               # Drop-in tool modules (auto-discovered)
│   │   ├── _template/       # Copy this to create a new tool
│   │   └── token_timer/     # PoC: brute-force feasibility calculator
│   └── utils/               # Shared helpers (subprocess streaming, etc.)
├── run.py                   # Dev entrypoint
├── Dockerfile               # python:3.12-slim + gunicorn
└── docker-compose.yml
```

## Adding a Tool

1. Copy `app/tools/_template/` to `app/tools/<your_slug>/`
2. Edit `__init__.py` — fill in `TOOL_MANIFEST` (slug must match dir name)
3. Edit `tool.html` — build your UI
4. Restart. That's it — no config files to touch.

See `NEW_TOOL_GUIDE.md` for full requirements.

## Routes

| Route                      | Purpose                          |
|----------------------------|----------------------------------|
| `GET /`                    | Dashboard with live search       |
| `GET /tools/<slug>`        | Individual tool page             |
| `GET /api/tools/search?q=` | JSON search (programmatic use)  |

## Design

- **Theme**: dark charcoal (`#0d0f12`), cyan (`#00d4aa`) / amber (`#f59e0b`) accents
- **Fonts**: JetBrains Mono (code), Syne (headings) — loaded from Google Fonts
- **Icons**: Lucide via CDN
- **No database, no ORM, no JS framework, no CSS framework**
