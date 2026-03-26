"""
Burp Suite Collaborator Client — Key Derivation Function (KDF) Reimplementation

Reverse-engineered from Burp Suite Professional JAR (obfuscated Java).

Algorithm summary:
  1. A BIID (Burp Interaction ID) is 32 cryptographically random bytes, Base64-encoded.
  2. A 22-character "key hash" is derived from the BIID via SHA-1 → base36 → check chars.
  3. Each subdomain payload is produced by a running-key cipher (additive base36 stream
     cipher) keyed by 2 random salt bytes, operating on the key hash concatenated with
     a version tag and hex counter nonce.
  4. The final subdomain is: salt(2) + check(1) + ciphertext(N).

Compatible with standard Burp Collaborator server polling at /burpresults?biid=<base64>.
"""

import os
import hashlib
import base64
import random
import string

ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
ALPHABET_LEN = len(ALPHABET)  # 36

# Lookup table: ASCII byte value → index in ALPHABET (or -1 if invalid)
_LOOKUP = [-1] * 128
for _i, _c in enumerate(ALPHABET):
    _LOOKUP[ord(_c)] = _i
    if _c.isalpha():
        _LOOKUP[ord(_c.upper())] = _i  # case-insensitive for A-Z


def _alphabet_index(b: int) -> int:
    """Return the base36 alphabet index for a byte value, or -1 if invalid."""
    if 0 <= b < 128:
        return _LOOKUP[b]
    return -1


def _bytes_to_base36(data: bytes) -> str:
    """Convert a byte array to a base36 string (big-endian, unsigned)."""
    num = int.from_bytes(data, byteorder="big", signed=False)
    if num == 0:
        return ALPHABET[0]
    chars = []
    while num > 0:
        num, digit = divmod(num, ALPHABET_LEN)
        chars.append(ALPHABET[digit])
    return "".join(reversed(chars))


def _check_char_from_string(s: str) -> str:
    """Compute the check character: alphabet[sum_of_ascii_values % 36]."""
    return ALPHABET[sum(ord(c) for c in s) % ALPHABET_LEN]


def _check_char_from_bytes(b0: int, b1: int) -> str:
    """Compute the check character from two raw byte values."""
    return ALPHABET[(b0 + b1) % ALPHABET_LEN]


def _compute_key_hash(biid_bytes: bytes) -> str:
    """
    Derive the 22-character key hash from 32 BIID bytes.

    Steps:
      1. SHA-1 hash the BIID bytes (20-byte digest)
      2. Convert to base36 string
      3. Take first 20 characters
      4. Split into two 10-char halves, append a check char to each
      5. Concatenate → 22-char result
    """
    digest = hashlib.sha1(biid_bytes).digest()
    base36_full = _bytes_to_base36(digest)
    first20 = base36_full[:20]
    half1 = first20[:10]
    half2 = first20[10:20]
    check1 = _check_char_from_string(half1)
    check2 = _check_char_from_string(half2)
    return half1 + check1 + half2 + check2


def _running_key_encrypt(salt: bytes, plaintext: str) -> str:
    """
    Additive base36 running-key cipher (Zf0.ZN equivalent).

    The cipher uses 2 alternating state bytes. For each input character,
    the output is alphabet[(index_of_input + index_of_state) % 36],
    and the state byte is updated to the output character.

    Args:
        salt: Exactly 2 bytes, each a valid base36 alphabet character.
        plaintext: String of base36 alphabet characters.

    Returns:
        Encrypted string of the same length.
    """
    state = list(salt)
    result = []
    for i, ch in enumerate(plaintext):
        idx = i % 2
        in_val = _alphabet_index(ord(ch))
        st_val = _alphabet_index(state[idx])
        out_val = (in_val + st_val) % ALPHABET_LEN
        out_ch = ALPHABET[out_val]
        state[idx] = ord(out_ch)
        result.append(out_ch)
    return "".join(result)


def generate_biid() -> str:
    """
    Generate a new BIID (Collaborator session secret key).

    Returns:
        Base64-encoded string of 32 cryptographically random bytes.
    """
    return base64.b64encode(os.urandom(32)).decode("ascii")


def derive_subdomain(biid: str, index: int, custom_data: str = "") -> str:
    """
    Derive the Nth subdomain prefix from a BIID.

    Args:
        biid: Base64-encoded 32-byte secret key.
        index: Zero-based counter (0, 1, 2, ...).
        custom_data: Optional alphanumeric string (max 16 chars) embedded in payload.

    Returns:
        DNS-safe subdomain string (lowercase alphanumeric, ~30 chars).
    """
    biid_bytes = base64.b64decode(biid)
    if len(biid_bytes) != 32:
        raise ValueError(f"BIID must decode to exactly 32 bytes, got {len(biid_bytes)}")

    if custom_data and (len(custom_data) > 16 or not all(c.isalnum() for c in custom_data)):
        raise ValueError("Custom data must be at most 16 alphanumeric characters")

    key_hash = _compute_key_hash(biid_bytes)

    # Nonce: hex(counter) + 'y' + custom_data
    nonce = f"{index:x}y{custom_data}"

    # Plaintext: key_hash + "1" (version hex) + "g" + nonce + "z"
    plaintext = key_hash + "1g" + nonce + "z"

    # Generate 2 random salt bytes from the base36 alphabet
    salt = bytes(ord(random.choice(ALPHABET)) for _ in range(2))

    # Encrypt
    ciphertext = _running_key_encrypt(salt, plaintext)

    # Check character from raw salt byte values
    check = _check_char_from_bytes(salt[0], salt[1])

    # Assemble: salt_char0 + salt_char1 + check + ciphertext
    return chr(salt[0]) + chr(salt[1]) + check + ciphertext


def make_payload(biid: str, index: int, server: str,
                 custom_data: str = "") -> str:
    """
    Return full payload domain: <derived_subdomain>.<server>

    Args:
        biid: Base64-encoded 32-byte secret key.
        index: Zero-based counter.
        server: Collaborator server hostname (e.g., "oastify.com").
        custom_data: Optional alphanumeric custom data.

    Returns:
        Full DNS payload like "ab3xyzabc123def456.oastify.com"
    """
    return derive_subdomain(biid, index, custom_data) + "." + server


# ---------------------------------------------------------------------------
# Internal helpers for testing / verification
# ---------------------------------------------------------------------------

def _derive_subdomain_deterministic(biid: str, index: int,
                                     salt: bytes,
                                     custom_data: str = "") -> str:
    """Same as derive_subdomain but with explicit salt (for testing)."""
    biid_bytes = base64.b64decode(biid)
    key_hash = _compute_key_hash(biid_bytes)
    nonce = f"{index:x}y{custom_data}"
    plaintext = key_hash + "1g" + nonce + "z"
    ciphertext = _running_key_encrypt(salt, plaintext)
    check = _check_char_from_bytes(salt[0], salt[1])
    return chr(salt[0]) + chr(salt[1]) + check + ciphertext


if __name__ == "__main__":
    # --- Verification against known Burp outputs ---

    # Test key: bytes 0..31
    test_key_bytes = bytes(range(32))
    test_biid = base64.b64encode(test_key_bytes).decode()
    print(f"Test BIID: {test_biid}")

    key_hash = _compute_key_hash(test_key_bytes)
    print(f"Key hash:  {key_hash}")
    assert key_hash == "unhzdwu2mz0o3nkrdbh203", f"Key hash mismatch: {key_hash}"

    # Test subdomain with salt ['a','a'], index 0, no custom data
    sub = _derive_subdomain_deterministic(test_biid, 0, b"aa")
    print(f"Subdomain(salt=aa, idx=0): {sub}")
    assert sub == "aaoun1c4yoq0fqtj6tnwo3gt9kfa3z", f"Subdomain mismatch: {sub}"

    # Test with salt ['x','3'], index 5
    sub2 = _derive_subdomain_deterministic(test_biid, 5, b"x3")
    print(f"Subdomain(salt=x3, idx=5): {sub2}")
    assert sub2 == "x31hgo5rrbjn8dm6zggjhq9g2782wr", f"Subdomain mismatch: {sub2}"

    # Test with custom data
    sub3 = _derive_subdomain_deterministic(test_biid, 2, b"aa", custom_data="test")
    print(f"Subdomain(salt=aa, idx=2, data=test): {sub3}")
    assert sub3 == "aaoun1c4yoq0fqtj6tnwo3gt9kfc3v7dq2", f"Subdomain mismatch: {sub3}"

    # All-zero key hash test
    zero_hash = _compute_key_hash(b"\x00" * 32)
    print(f"Zero key hash: {zero_hash}")
    assert zero_hash == "z93539brtrfel4u9fmlw94", f"Zero hash mismatch: {zero_hash}"

    print("\n--- All assertions passed ---\n")

    # Demo: generate a fresh BIID and payloads
    biid = generate_biid()
    print(f"Generated BIID: {biid}")
    print(f"Key hash:       {_compute_key_hash(base64.b64decode(biid))}")
    for i in range(5):
        print(f"  Subdomain {i}: {derive_subdomain(biid, i)}")
    print(f"  Full payload: {make_payload(biid, 0, 'oastify.com')}")
