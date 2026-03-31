"""
Editable substitution rules for pronounceable password fragments.

Each character is replaced with another character of the same class:
  - vowels (a, e, i, o, u, and vowel-like y) → only from that letter's vowel pool
  - consonants → only from that letter's consonant pool

Edit the pools below to bias toward certain sounds. Each character in a pool is
equally likely unless you change selection logic in ``wordlist.transform_word``.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Vowel pools (only vowels; pronounceability preserved by staying in vowel space)
# ---------------------------------------------------------------------------
VOWEL_DEFAULT = "aeiou"

VOWEL_POOLS: dict[str, str] = {
    "a": "aeiou",
    "e": "aeiou",
    "i": "aeiou",
    "o": "aeiou",
    "u": "aeiou",
    # y when it acts as a vowel (see wordlist._is_vowel)
    "y": "aeiouy",
}

# ---------------------------------------------------------------------------
# Consonant pools — phonetically similar groups where possible; edit freely.
# Keys must cover consonants; unknown letters fall back to CONSONANT_DEFAULT.
# ---------------------------------------------------------------------------
CONSONANT_DEFAULT = "bcdfghjklmnpqrstvwxyz"

CONSONANT_POOLS: dict[str, str] = {
    "b": "bpm",
    "c": "ckq",
    "d": "dtn",
    "f": "fvh",
    "g": "gjk",
    "h": "hf",
    "j": "jg",
    "k": "ckq",
    "l": "lrw",
    "m": "mn",
    "n": "mnt",
    "p": "bpm",
    "q": "ckq",
    "r": "rwl",
    "s": "sz",
    "t": "dtn",
    "v": "vfw",
    "w": "wlr",
    "x": "xksz",
    "z": "zjs",
    # y when word-initial (consonantal), e.g. "yes"
    "y": "yhj",
}
