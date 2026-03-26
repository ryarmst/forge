"""
Collaborator Client — server-side endpoints.

Provides:
  POST /api/generate-biid   — create a new BIID + key hash
  POST /api/derive-payload  — derive a subdomain from a BIID + counter
  POST /api/poll            — proxy poll requests to the Collaborator server
"""

import json
import re
import ssl
import urllib.parse
import urllib.request
import urllib.error

from flask import Blueprint, request, jsonify

from app.tools.collab_client.kdf import (
    generate_biid,
    compute_key_hash,
    derive_subdomain,
    make_payload,
)
import base64

blueprint = Blueprint("collab_client", __name__)

_HOSTNAME_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$"
)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _body_preview(raw, max_len=2000):
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        text = repr(raw)
    if len(text) > max_len:
        text = text[:max_len] + "... [truncated]"
    return text


# ── BIID Generation ──────────────────────────────────────────────────────────

@blueprint.route("/api/generate-biid", methods=["POST"])
def api_generate_biid():
    """Generate a new BIID and return it with its key hash."""
    biid = generate_biid()
    biid_bytes = base64.b64decode(biid)
    key_hash = compute_key_hash(biid_bytes)
    return jsonify({"biid": biid, "key_hash": key_hash})


# ── Payload Derivation ───────────────────────────────────────────────────────

@blueprint.route("/api/derive-payload", methods=["POST"])
def api_derive_payload():
    """Derive one or more subdomain payloads from a BIID."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    biid = (data.get("biid") or "").strip()
    server = (data.get("server") or "").strip()
    start = data.get("index", 0)
    count = data.get("count", 1)

    if not biid:
        return jsonify({"error": "Missing BIID"}), 400

    try:
        biid_bytes = base64.b64decode(biid)
        if len(biid_bytes) != 32:
            raise ValueError("bad length")
    except Exception:
        return jsonify({"error": "Invalid BIID (must be 32 bytes, Base64-encoded)"}), 400

    count = min(max(int(count), 1), 50)
    results = []
    for i in range(count):
        idx = int(start) + i
        sub = derive_subdomain(biid, idx)
        full = (sub + "." + server) if server else sub
        results.append({"index": idx, "subdomain": sub, "payload": full})

    return jsonify({"payloads": results})


# ── Poll Proxy ───────────────────────────────────────────────────────────────

@blueprint.route("/api/poll", methods=["POST"])
def poll():
    """Proxy a poll request to the Collaborator server."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing request body", "debug": {}}), 400

    biid = (data.get("biid") or "").strip()
    server = (data.get("server") or "").strip()
    port = data.get("port", 9443)

    if not biid:
        return jsonify({"error": "Missing BIID", "debug": {}}), 400
    if not server or not _HOSTNAME_RE.match(server):
        return jsonify({"error": "Invalid server hostname", "debug": {"server": server}}), 400

    try:
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid port", "debug": {"port": str(port)}}), 400

    protocol = data.get("protocol", "https").lower()
    if protocol not in ("http", "https"):
        protocol = "https"

    encoded_biid = urllib.parse.quote(biid, safe="")
    url = f"{protocol}://{server}:{port}/burpresults?biid={encoded_biid}"

    debug = {
        "url": url,
        "biid_raw": biid,
        "biid_encoded": encoded_biid,
        "protocol": protocol,
        "server": server,
        "port": port,
    }

    try:
        req = urllib.request.Request(url, headers={"Connection": "close"})
        resp = urllib.request.urlopen(req, context=_SSL_CTX, timeout=15)
        debug["status"] = resp.status
        debug["headers"] = dict(resp.headers)
        body = resp.read()
        debug["body_length"] = len(body)
        debug["body_raw"] = _body_preview(body)

    except urllib.error.HTTPError as exc:
        err_body = b""
        try:
            err_body = exc.read()
        except Exception:
            pass
        debug["status"] = exc.code
        debug["body_raw"] = _body_preview(err_body)
        debug["body_length"] = len(err_body)
        return jsonify({"error": f"Server returned HTTP {exc.code}", "debug": debug}), 502

    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        debug["error_type"] = "URLError"
        debug["error_detail"] = reason
        return jsonify({"error": f"Connection failed: {reason}", "debug": debug}), 502

    except Exception as exc:
        debug["error_type"] = type(exc).__name__
        debug["error_detail"] = str(exc)
        return jsonify({"error": f"Poll failed: {type(exc).__name__}: {exc}", "debug": debug}), 500

    if not body or body.strip() in (b"{}", b""):
        debug["parsed"] = "empty/no interactions"
        return jsonify({"responses": [], "debug": debug})

    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        debug["parse_error"] = str(exc)
        return jsonify({"error": "Server response is not valid JSON", "debug": debug}), 502

    debug["parsed"] = f"{len(result.get('responses', []))} interaction(s)"
    if "responses" not in result:
        result = {"responses": []}
    result["debug"] = debug
    return jsonify(result)
