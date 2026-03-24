"""
Core routes blueprint — dashboard, tool rendering, and search API.
"""

from flask import Blueprint, render_template, request, jsonify, current_app, abort

core = Blueprint("core", __name__)


@core.route("/")
def index():
    """Dashboard page with tool grid and live search."""
    registry = current_app.jinja_env.globals["tool_registry"]
    return render_template("index.html", tools=registry.tools, tools_json=registry.to_json())


@core.route("/tools/<slug>")
def tool_page(slug):
    """Render a specific tool's page inside tool_base.html."""
    registry = current_app.jinja_env.globals["tool_registry"]
    tool = registry.get(slug)
    if tool is None:
        abort(404)
    return render_template(f"tools/{slug}/tool.html", tool=tool)


@core.route("/api/tools/search")
def search_tools():
    """JSON search endpoint for programmatic use."""
    query = request.args.get("q", "").strip()
    registry = current_app.jinja_env.globals["tool_registry"]
    results = registry.search(query)
    return jsonify([
        {
            "name": t.name,
            "slug": t.slug,
            "version": t.version,
            "description": t.description,
            "tags": t.tags,
            "author": t.author,
            "has_server_logic": t.has_server_logic,
            "icon": t.icon,
        }
        for t in results
    ])
