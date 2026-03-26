# New Tool Guide

## Minimum Viable Tool (2 files)

```
app/tools/my_tool/
├── __init__.py    # TOOL_MANIFEST dict (required)
└── tool.html      # UI template (required)
```

No registration step. Drop the directory in, push, done.

## Requirements

### __init__.py

Must export a `TOOL_MANIFEST` dict with **all** of these keys:

| Key                | Type       | Rule                                      |
|--------------------|------------|-------------------------------------------|
| `name`             | str        | Human-readable display name               |
| `slug`             | str        | **Must match directory name exactly**      |
| `version`          | str        | Semver (e.g. `"1.0.0"`)                   |
| `description`      | str        | 1-2 sentences (used for search)           |
| `tags`             | list[str]  | Lowercase keywords (use only 1-3 very relevant ones) (used for search)      |
| `has_server_logic` | bool       | `True` only if you have a `routes.py`     |

### tool.html

- Must extend `tool_base.html` and fill `{% block tool_content %}`
- The `tool` variable (manifest data) is available in context
- JS goes in inline `<script>` tags — vanilla only
- CSS goes in inline `<style>` tags — use theme variables (see below)

### routes.py (only if has_server_logic = True)

- Must expose a variable called `blueprint` (Flask Blueprint)
- Blueprint name must match slug
- Routes are relative — prefix `/tools/<slug>/` is applied automatically
- Convention: `POST /api/run` for the main action endpoint

## Available Theme Variables

```css
--bg: #0d0f12          --accent: #00d4aa
--surface: #161a1f     --accent-warm: #f59e0b
--surface-2: #1e232a   --danger: #ef4444
--border: #2a2f38      --font-mono: 'JetBrains Mono'
--text: #c8cdd6        --font-display: 'Syne'
--text-muted: #5a6172
```

## Limitations & Restrictions

- **No JS frameworks** (React, Vue, jQuery, etc.)
- **No CSS frameworks** (Bootstrap, Tailwind, etc.)
- **No database access** — tools must be stateless
- **No file system writes** — tools should not persist data to disk
- **No `eval()`, `exec()`, or `shell=True`** in any Python code
- **No unsanitized user input** in subprocess commands or templates
- **Slug must be a valid Python identifier** (lowercase, underscores, no hyphens)
- **Directory names starting with `_`** are ignored by auto-discovery
- External binaries (nmap, waymore, etc.) must be installed in the Dockerfile
- Long-running server tools should use SSE streaming via `app.utils.subprocess_runner`
- Prefix tool-specific CSS classes with your slug to avoid style collisions

## Quick Copy-Paste Start

```bash
cp -r app/tools/_template app/tools/my_new_tool
# Edit __init__.py — set slug to "my_new_tool", fill all fields
# Edit tool.html — build your UI
# Delete routes.py if client-only (and set has_server_logic: False)
# Push to deploy
```
