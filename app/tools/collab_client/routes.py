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
import urllib.error

from flask import Blueprint, request, jsonify

blueprint = Blueprint("collab_client", __name__)

_HOSTNAME_RE = re.compile(
    r"^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*$"
)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _body_preview(raw, max_len=2000):
    """Return a truncated UTF-8 preview of a response body."""
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        text = repr(raw)
    if len(text) > max_len:
        text = text[:max_len] + "... [truncated]"
    return text


@blueprint.route("/api/poll", methods=["POST"])
def poll():
    """Proxy a poll request to the Collaborator server.

    Always returns a debug object with full request/response details
    so the client-side debug log can display them.
    """
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
