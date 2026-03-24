"""
Blueprint routes for this tool.
Only needed when TOOL_MANIFEST["has_server_logic"] is True.

The blueprint name MUST match the tool slug.
URL prefix is auto-registered as /tools/<slug>/ by the app factory.
"""

from flask import Blueprint, request, jsonify, render_template

blueprint = Blueprint("my_tool_name", __name__)


@blueprint.route("/")
def index():
    """Render the tool's main page."""
    return render_template("tools/my_tool_name/tool.html")


@blueprint.route("/api/run", methods=["POST"])
def run():
    """Execute the tool's server-side logic and return results."""
    data = request.get_json()
    # ... tool logic here ...
    return jsonify({"result": "..."})
