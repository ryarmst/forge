"""
Pronounceable Password Generator — server-side endpoint.

POST /api/generate
Returns a password formatted as:
  <word>$<word>$<word><digit><digit>
"""

import secrets

from flask import Blueprint, jsonify, request

from app.tools.password_generator.wordlist_mod import MODIFIED_WORDS

blueprint = Blueprint("password_generator", __name__)


def _generate_one_password() -> str:
    # Use cryptographically-strong randomness.
    w1 = secrets.choice(MODIFIED_WORDS)
    w2 = secrets.choice(MODIFIED_WORDS)
    w3 = secrets.choice(MODIFIED_WORDS)
    d1 = secrets.randbelow(10)
    d2 = secrets.randbelow(10)
    return f"{w1}${w2}${w3}{d1}{d2}"


@blueprint.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}
    count = data.get("count", 1)
    try:
        count = int(count)
    except Exception:
        count = 1

    count = max(1, min(count, 20))

    passwords = [_generate_one_password() for _ in range(count)]
    if count == 1:
        return jsonify({"password": passwords[0]})
    return jsonify({"passwords": passwords})

