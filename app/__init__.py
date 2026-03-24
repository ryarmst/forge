"""
Flask application factory for Forge -- the security testing tools platform.
"""

import os

from flask import Flask, render_template, jsonify, request
from jinja2 import ChoiceLoader, FileSystemLoader

from app.routes import core
from app.tool_registry import ToolRegistry


def create_app() -> Flask:
    app = Flask(__name__)

    # Let Jinja2 resolve paths like "tools/token_timer/tool.html" by adding
    # the app package directory as a secondary template search path.
    app_root = os.path.dirname(__file__)
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,
        FileSystemLoader(app_root),
    ])

    # --- Tool discovery ---
    registry = ToolRegistry()
    registry.discover()
    app.jinja_env.globals["tool_registry"] = registry

    # --- Register core routes blueprint ---
    app.register_blueprint(core)

    # --- Register each tool's blueprint (if it has server-side routes) ---
    for tool in registry.tools:
        if tool.blueprint is not None:
            app.register_blueprint(tool.blueprint, url_prefix=f"/tools/{tool.slug}")

    # --- Security headers ---
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    # --- Error handlers ---
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("404.html", error="Something went wrong."), 500

    return app
