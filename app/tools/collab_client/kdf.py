"""
Burp Collaborator — Key Derivation Function.

Generates BIIDs and derives DNS-safe subdomain payloads compatible with
standard Burp Collaborator servers (polling at /burpresults?biid=<base64>).

Algorithm: SHA-1 key hash + polyalphabetic additive stream cipher in Z36.
"""

import os
import hashlib
import base64
import random

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
ALPHABET_LEN = 36

_LOOKUP = [-1] * 128
for _i, _c in enumerate(ALPHABET):
    _LOOKUP[ord(_c)] = _i
    if _c.isalpha():
        _LOOKUP[ord(_c.upper())] = _i


def _alpha_idx(b):
    return _LOOKUP[b] if 0 <= b < 128 else -1


def _bytes_to_base36(data):
    num = int.from_bytes(data, byteorder="big", signed=False)
    if num == 0:
        return ALPHABET[0]
    chars = []
    while num > 0:
        num, digit = divmod(num, ALPHABET_LEN)
        chars.append(ALPHABET[digit])
    return "".join(reversed(chars))


def _check_char(s):
    return ALPHABET[sum(ord(c) for c in s) % ALPHABET_LEN]


def _check_char_bytes(b0, b1):
    return ALPHABET[(b0 + b1) % ALPHABET_LEN]


def compute_key_hash(biid_bytes):
    """Derive the 22-char key hash from 32 BIID bytes (SHA-1 -> base36 + check chars)."""
    digest = hashlib.sha1(biid_bytes).digest()
    b36 = _bytes_to_base36(digest)
    first20 = b36[:20]
    h1, h2 = first20[:10], first20[10:20]
    return h1 + _check_char(h1) + h2 + _check_char(h2)


def _encrypt(salt, plaintext):
    """Running-key additive cipher in Z36 with 2 alternating state registers."""
    state = list(salt)
    out = []
    for i, ch in enumerate(plaintext):
        idx = i % 2
        iv = _alpha_idx(ord(ch))
        sv = _alpha_idx(state[idx])
        ov = (iv + sv) % ALPHABET_LEN
        oc = ALPHABET[ov]
        state[idx] = ord(oc)
        out.append(oc)
    return "".join(out)


def generate_biid():
    """Generate a new BIID: 32 cryptographically random bytes, Base64-encoded."""
    return base64.b64encode(os.urandom(32)).decode("ascii")


def derive_subdomain(biid, index, custom_data=""):
    """
    Derive the Nth subdomain prefix from a BIID.

    Returns a DNS-safe string (~30 chars, lowercase alphanumeric).
    """
    biid_bytes = base64.b64decode(biid)
    if len(biid_bytes) != 32:
        raise ValueError(f"BIID must decode to 32 bytes, got {len(biid_bytes)}")
    if custom_data and (len(custom_data) > 16 or not all(c.isalnum() for c in custom_data)):
        raise ValueError("Custom data must be at most 16 alphanumeric characters")

    key_hash = compute_key_hash(biid_bytes)
    nonce = f"{index:x}y{custom_data}"
    plaintext = key_hash + "1g" + nonce + "z"

    salt = bytes(ord(random.choice(ALPHABET)) for _ in range(2))
    ciphertext = _encrypt(salt, plaintext)
    check = _check_char_bytes(salt[0], salt[1])
    return chr(salt[0]) + chr(salt[1]) + check + ciphertext


def make_payload(biid, index, server, custom_data=""):
    """Return full domain: <derived_subdomain>.<server>"""
    return derive_subdomain(biid, index, custom_data) + "." + server
