"""
Editable substitution rules for pronounceable password fragments.

Each character is replaced with another character of the same class:
  - vowels → only from that letter's vowel pool
  - consonants → only from that letter's consonant pool

Exactly one change per word (see ``wordlist.transform_word``): either a single
letter swap (vowel/consonant pools above) **or** collapsing a consonant digraph
(two letters, one combined sound) into **one** consonant from the digraph pool.
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

# ---------------------------------------------------------------------------
# Consonant digraphs → one replacement consonant (string = pool of choices).
# Only two-letter keys; each replacement must be a single lowercase letter.
# Edit freely: add pairs (e.g. "ll" → "l" is optional) or narrow pools.
# ---------------------------------------------------------------------------
CONSONANT_DIGRAPH_POOLS: dict[str, str] = {
    "sh": "szc",
    "ch": "cktj",
    "th": "td",
    "ph": "fv",
    "wh": "hw",
    "ck": "kc",
    "ng": "nm",
    "kn": "nk",
    "wr": "rw",
    "mb": "m",
    "dg": "jd",
    "qu": "kw",
    "sc": "skc",
    "gh": "fg",
    "rh": "r",
    "ps": "spt",
}
