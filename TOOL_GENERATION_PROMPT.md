# Forge Tool Generation Prompt

Use this prompt (or feed it to an LLM) to generate a new Forge tool module.

---

## Prompt

```
Generate a Forge tool module. Forge is a Flask-based security tools platform.
Each tool lives in its own directory under app/tools/<slug>/ and is auto-discovered at startup.

OUTPUT THESE FILES:

1. app/tools/<slug>/__init__.py — Must export exactly this dict:

    TOOL_MANIFEST = {
        "name": str,              # Display name
        "slug": str,              # URL-safe ID, MUST match directory name
        "version": str,           # Semver
        "description": str,       # 1-2 sentences for search indexing
        "tags": list[str],        # Lowercase keywords for search
        "author": str,
        "has_server_logic": bool, # True only if routes.py exists
        "icon": str,              # Lucide icon name (https://lucide.dev/icons/)
    }

2. app/tools/<slug>/tool.html — Jinja2 template:

    {% extends "tool_base.html" %}
    {% block tool_content %}
      <!-- Your UI here. tool_base.html provides nav, sidebar, breadcrumb. -->
      <!-- The 'tool' object (manifest fields) is available in template context. -->
    {% endblock %}

    Rules:
    - Vanilla JS only (no React/Vue/jQuery). Inline <script> at bottom of block.
    - Use CSS classes prefixed with your slug (e.g. .mytool-panel) to avoid collisions.
    - Use CSS variables from the theme: --bg, --surface, --surface-2, --border,
      --text, --text-muted, --accent, --accent-warm, --danger,
      --font-mono ('JetBrains Mono'), --font-display ('Syne').
    - Lucide icons: <i data-lucide="icon-name"></i> (already loaded globally).
    - For client-only tools: all logic in <script> tags, has_server_logic: False.
    - For server-backed tools: also create routes.py (see below).

3. app/tools/<slug>/routes.py — ONLY if has_server_logic is True:

    from flask import Blueprint, request, jsonify, render_template

    blueprint = Blueprint("<slug>", __name__)

    @blueprint.route("/api/run", methods=["POST"])
    def run():
        data = request.get_json()
        # Tool logic here. NEVER use eval/exec/shell=True.
        return jsonify({"result": ...})

    Rules:
    - Blueprint variable MUST be named 'blueprint'.
    - Blueprint name MUST match the slug.
    - URL prefix /tools/<slug>/ is auto-registered — your routes are relative.
    - For subprocess tools, use: from app.utils.subprocess_runner import stream_response
    - Return streaming SSE for long-running processes.

CONSTRAINTS:
- No external JS/CSS frameworks. No database. No file writes.
- Never use eval(), exec(), or shell=True in subprocess calls.
- All user inputs must be validated/sanitized before use.
- Inline <style> blocks are fine for tool-specific CSS.

DESCRIBE THE TOOL:
[Insert your tool description here — what it does, inputs, outputs, math/logic.]
```
