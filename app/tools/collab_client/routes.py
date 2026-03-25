"""
Collaborator Client — server-side poll proxy.

The browser can't directly hit the Collaborator polling endpoint due to CORS
and self-signed certificate issues. This blueprint proxies those requests.
"""

import json
import re
import ssl
import urllib.parse
import urllib.request

from flask import Blueprint, request, jsonify

blueprint = Blueprint("collab_client", __name__)

_HOSTNAME_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$"
)

# Reusable SSL context — Collaborator servers typically use self-signed certs
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


@blueprint.route("/api/poll", methods=["POST"])
def poll():
    """Proxy a poll request to the Collaborator server."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    biid = (data.get("biid") or "").strip()
    server = (data.get("server") or "").strip()
    port = data.get("port", 9443)

    if not biid:
        return jsonify({"error": "Missing BIID"}), 400
    if not server or not _HOSTNAME_RE.match(server):
        return jsonify({"error": "Invalid server hostname"}), 400

    try:
        port = int(port)
        if not 1 <= port <= 65535:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid port"}), 400

    encoded_biid = urllib.parse.quote(biid, safe="")
    url = f"https://{server}:{port}/burpresults?biid={encoded_biid}"

    try:
        req = urllib.request.Request(url, headers={"Connection": "close"})
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
            body = resp.read()

        if not body or body.strip() in (b"{}", b""):
            return jsonify({"responses": []})

        result = json.loads(body)
        if "responses" not in result:
            result = {"responses": []}
        return jsonify(result)

    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        return jsonify({"error": f"Connection failed: {reason}"}), 502
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON from server"}), 502
    except Exception as exc:
        return jsonify({"error": f"Poll failed: {str(exc)}"}), 500
