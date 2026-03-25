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

# Reusable SSL context — Collaborator servers typically use self-signed certs
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _body_preview(raw, max_len=500):
    """Return a truncated UTF-8 preview of a response body for diagnostics."""
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        text = repr(raw)
    if len(text) > max_len:
        text = text[:max_len] + "... [truncated]"
    return text


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

    protocol = data.get("protocol", "https").lower()
    if protocol not in ("http", "https"):
        protocol = "https"

    encoded_biid = urllib.parse.quote(biid, safe="")
    url = f"{protocol}://{server}:{port}/burpresults?biid={encoded_biid}"

    try:
        req = urllib.request.Request(url, headers={"Connection": "close"})
        resp = urllib.request.urlopen(req, context=_SSL_CTX, timeout=15)
        status = resp.status
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read()

    except urllib.error.HTTPError as exc:
        # Server returned a non-2xx status — read the error body for diagnostics
        err_body = b""
        try:
            err_body = exc.read()
        except Exception:
            pass
        return jsonify({
            "error": f"Server returned HTTP {exc.code}",
            "debug": {
                "url": url,
                "status": exc.code,
                "body_preview": _body_preview(err_body),
            },
        }), 502

    except urllib.error.URLError as exc:
        reason = str(getattr(exc, "reason", exc))
        return jsonify({
            "error": f"Connection failed: {reason}",
            "debug": {"url": url},
        }), 502

    except Exception as exc:
        return jsonify({
            "error": f"Poll failed: {type(exc).__name__}: {exc}",
            "debug": {"url": url},
        }), 500

    # Empty or `{}` response means no interactions
    if not body or body.strip() in (b"{}", b""):
        return jsonify({"responses": [], "debug": {"url": url, "status": status}})

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        return jsonify({
            "error": "Server response is not valid JSON",
            "debug": {
                "url": url,
                "status": status,
                "content_type": content_type,
                "body_preview": _body_preview(body),
            },
        }), 502

    if "responses" not in result:
        result = {"responses": []}
    result["debug"] = {"url": url, "status": status}
    return jsonify(result)
