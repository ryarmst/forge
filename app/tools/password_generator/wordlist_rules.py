"""
Editable substitution rules for pronounceable password fragments.

Each character is replaced with another character of the same class:
  - vowels → only from that letter's vowel pool
  - consonants → only from that letter's consonant pool

Why outputs used to look like ``qfomnuwz``:
  * Every letter was swapped independently, so syllable shape was destroyed.
  * Pools such as ``ckq`` and ``sz`` inject ``q`` and ``z`` at high rates when
    ``c``/``k``/``s`` are common.
  * ``lrw`` / ``rwl`` inject ``w`` in places English rarely uses it.
  * ``CONSONANT_DEFAULT`` included ``q``, ``x``, ``z``, so any unmapped letter
    could become those.

One letter per word is substituted at random (see ``wordlist.transform_word``).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Vowel pools (vowels only)
# ---------------------------------------------------------------------------
VOWEL_DEFAULT = "aeiou"

VOWEL_POOLS: dict[str, str] = {
    "a": "aeiou",
    "e": "aeiou",
    "i": "aeiou",
    "o": "aeiou",
    "u": "aeiou",
    "y": "aeiouy",
}

# ---------------------------------------------------------------------------
# Consonant pools — favor letters that fit English-like chunks; no ``q`` in
# ``c``/``k`` pools, no ``z`` in ``s`` pool, etc. Rare letters only map to
# mild alternates.
# ---------------------------------------------------------------------------
# Fallback when a letter has no entry (should not happen for a–z).
CONSONANT_DEFAULT = "bcdfghjklmnprstv"

CONSONANT_POOLS: dict[str, str] = {
    "b": "bpm",
    "c": "ck",
    "d": "dtn",
    "f": "fv",
    "g": "gk",
    "h": "hf",
    "j": "jg",
    "k": "ck",
    "l": "lr",
    "m": "mn",
    "n": "mnt",
    "p": "bpm",
    "q": "ckw",
    "r": "lr",
    "s": "st",
    "t": "dtn",
    "v": "fv",
    "w": "lr",
    "x": "ks",
    "z": "st",
    "y": "hj",
}
