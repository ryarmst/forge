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


def _digraph_starts(word_lower: str) -> list[int]:
    """Start indices where ``word_lower[i : i + 2]`` is a known digraph."""
    pools = getattr(rules, "CONSONANT_DIGRAPH_POOLS", None) or {}
    n = len(word_lower)
    out: list[int] = []
    for i in range(n - 1):
        pair = word_lower[i : i + 2]
        pool = pools.get(pair)
        if not pool:
            continue
        a, b = pair[0], pair[1]
        if not (a.isalpha() and b.isalpha()):
            continue
        if all(len(c) == 1 and c.isalpha() for c in pool):
            out.append(i)
    return out


def _apply_digraph(word_lower: str, start: int) -> str:
    pools = getattr(rules, "CONSONANT_DIGRAPH_POOLS", None) or {}
    pair = word_lower[start : start + 2]
    repl = secrets.choice(pools[pair])
    return word_lower[:start] + repl + word_lower[start + 2 :]


def transform_word(word: str) -> str:
    """
    Apply exactly one random change (if possible): either a single-letter
    vowel/consonant swap, or collapsing a consonant digraph to one letter,
    then capitalize the first letter.
    """
    raw = word.strip()
    if not raw:
        return raw

    lower_full = raw.lower()
    single_idxs = [
        i
        for i, c in enumerate(lower_full)
        if c.isalpha() and _can_modify(lower_full, i)
    ]
    digraph_idxs = _digraph_starts(lower_full)

    options: list[tuple[str, int]] = [("single", i) for i in single_idxs]
    options.extend(("digraph", i) for i in digraph_idxs)

    if options:
        kind, idx = secrets.choice(options)
        if kind == "digraph":
            body = _apply_digraph(lower_full, idx)
        else:
            chars = list(lower_full)
            ch = chars[idx]
            pool = _pool_for(lower_full, idx, ch)
            chars[idx] = _pick_from_pool(pool, ch)
            body = "".join(chars)
    else:
        body = lower_full

    return body[0].upper() + body[1:] if body else body
