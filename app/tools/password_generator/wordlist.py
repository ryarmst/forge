"""
Filtered English word list + runtime vowel/consonant-preserving transforms.

Words are loaded from ``words.txt`` (4–9 characters, from Google 10k USA list).
"""

from __future__ import annotations

import secrets
from pathlib import Path

from app.tools.password_generator import wordlist_rules as rules

_PKG = Path(__file__).resolve().parent
_RNG = secrets.SystemRandom()


def _load_raw_words() -> tuple[str, ...]:
    path = _PKG / "words.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.lower())
    return tuple(out)


RAW_WORDS: tuple[str, ...] = _load_raw_words()


def _is_vowel(c: str, index: int, word: str) -> bool:
    """Classify vowels vs consonants; y is consonant at word start, else vowel."""
    cc = c.lower()
    if cc in "aeiou":
        return True
    if cc == "y":
        return index != 0
    return False


def _pick_from_pool(pool: str, original: str) -> str:
    """Random choice; prefer a different letter than ``original`` when possible."""
    o = original.lower()
    alts = [x for x in pool if x.lower() != o]
    if alts:
        return secrets.choice(alts)
    return secrets.choice(pool)


def transform_word(word: str) -> str:
    """
    Replace letters (probabilistically) using vowel/consonant pools from rules.

    Preserves non-letters and case (per-character).
    """
    v_chance = float(getattr(rules, "VOWEL_REPLACE_CHANCE", 1.0))
    c_chance = float(getattr(rules, "CONSONANT_REPLACE_CHANCE", 1.0))
    v_chance = max(0.0, min(1.0, v_chance))
    c_chance = max(0.0, min(1.0, c_chance))

    out: list[str] = []
    for i, c in enumerate(word):
        if not c.isalpha():
            out.append(c)
            continue
        lower = c.lower()
        if _is_vowel(lower, i, word):
            if _RNG.random() >= v_chance:
                repl = lower
            else:
                pool = rules.VOWEL_POOLS.get(lower, rules.VOWEL_DEFAULT)
                repl = _pick_from_pool(pool, lower)
        else:
            if _RNG.random() >= c_chance:
                repl = lower
            else:
                pool = rules.CONSONANT_POOLS.get(lower, rules.CONSONANT_DEFAULT)
                repl = _pick_from_pool(pool, lower)
        if c.isupper():
            repl = repl.upper()
        out.append(repl)
    return "".join(out)
