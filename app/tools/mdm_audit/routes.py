"""
MDM Profile Auditor — server-side endpoints.

POST /api/analyse   — upload a profile, get back an HTML report
GET  /api/reference — download the default restriction_reference.yaml
"""

import os

from flask import Blueprint, request, jsonify, send_file

from app.tools.mdm_audit.analyser import (
    parse_profile,
    extract_restrictions,
    load_reference_yaml,
    analyse_deprecated,
    analyse_insecure,
    analyse_conflicts,
    extract_apps,
    build_report_html,
)

blueprint = Blueprint("mdm_audit", __name__)

_TOOL_DIR = os.path.dirname(__file__)
_DEFAULT_REF = os.path.join(_TOOL_DIR, "restriction_reference.yaml")

ALLOWED_EXTENSIONS = (".xml", ".mobileconfig", ".plist")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@blueprint.route("/api/reference", methods=["GET"])
def get_reference():
    """Serve the default restriction_reference.yaml for download."""
    return send_file(
        _DEFAULT_REF,
        mimetype="text/yaml",
        as_attachment=True,
        download_name="restriction_reference.yaml",
    )


@blueprint.route("/api/analyse", methods=["POST"])
def analyse():
    """Accept an uploaded profile, run analysis, return JSON with HTML report."""
    if "profile" not in request.files:
        return jsonify({"error": "No profile file uploaded"}), 400

    f = request.files["profile"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type '{ext}'. Use .xml, .mobileconfig, or .plist"}), 400

    raw = f.read()
    if len(raw) > MAX_FILE_SIZE:
        return jsonify({"error": "File exceeds 5 MB limit"}), 400
    if not raw:
        return jsonify({"error": "File is empty"}), 400

    ref_file = request.files.get("reference")
    if ref_file and ref_file.filename:
        ref_text = ref_file.read().decode("utf-8", errors="replace")
    else:
        with open(_DEFAULT_REF, "r") as rf:
            ref_text = rf.read()

    try:
        profile = parse_profile(raw)
    except Exception as exc:
        return jsonify({"error": f"Failed to parse profile: {exc}"}), 400

    try:
        ref, rules = load_reference_yaml(ref_text)
    except Exception as exc:
        return jsonify({"error": f"Failed to parse reference YAML: {exc}"}), 400

    restrictions, meta = extract_restrictions(profile)
    deprecated = analyse_deprecated(restrictions, ref)
    insecure = analyse_insecure(restrictions, ref)
    conflicts = analyse_conflicts(restrictions, rules)
    allowed_ids, blocked_ids = extract_apps(restrictions)

    total_insecure = sum(len(v) for v in insecure.values())

    html = build_report_html(
        meta, deprecated, insecure, conflicts,
        allowed_ids, blocked_ids, f.filename,
    )

    return jsonify({
        "html": html,
        "summary": {
            "profile_name": meta.get("PayloadDisplayName", "Unknown"),
            "restriction_count": len(restrictions),
            "deprecated": len(deprecated),
            "insecure": total_insecure,
            "conflicts": len(conflicts),
            "allowed_apps": len(allowed_ids),
            "blocked_apps": len(blocked_ids),
        },
    })
