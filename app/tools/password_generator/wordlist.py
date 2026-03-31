"""
Filtered English word list + runtime vowel/consonant-preserving transforms.

Words are loaded from ``words.txt`` (4–9 characters, from Google 10k USA list).
"""

from __future__ import annotations

import secrets
from pathlib import Path

from app.tools.password_generator import wordlist_rules as rules

_PKG = Path(__file__).resolve().parent


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


def _pool_for(word_lower: str, index: int, ch: str) -> str:
    if _is_vowel(ch, index, word_lower):
        return rules.VOWEL_POOLS.get(ch, rules.VOWEL_DEFAULT)
    return rules.CONSONANT_POOLS.get(ch, rules.CONSONANT_DEFAULT)


def _can_modify(word_lower: str, index: int) -> bool:
    ch = word_lower[index]
    if not ch.isalpha():
        return False
    pool = _pool_for(word_lower, index, ch)
    return any(x.lower() != ch for x in pool)


def _pick_from_pool(pool: str, original: str) -> str:
    """Random choice; prefer a different letter than ``original`` when possible."""
    o = original.lower()
    alts = [x for x in pool if x.lower() != o]
    if alts:
        return secrets.choice(alts)
    return secrets.choice(pool)


def transform_word(word: str) -> str:
    """
    Apply exactly one random vowel/consonant-preserving substitution (if any
    position can change), then capitalize the first letter.
    """
    raw = word.strip()
    if not raw:
        return raw

    lower_full = raw.lower()
    modifiable = [
        i
        for i, c in enumerate(lower_full)
        if c.isalpha() and _can_modify(lower_full, i)
    ]
    chars = list(lower_full)
    if modifiable:
        idx = secrets.choice(modifiable)
        ch = chars[idx]
        pool = _pool_for(lower_full, idx, ch)
        chars[idx] = _pick_from_pool(pool, ch)

    body = "".join(chars)
    return body[0].upper() + body[1:] if body else body
