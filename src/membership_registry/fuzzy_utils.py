"""Fuzzy search helpers: tolerate typos like 'Sntos' -> 'Santos'.

Strategy (kept stdlib-only via difflib):
  1. Exact SQL LIKE search runs first (fast, precise, digit-normalized).
  2. If it returns fewer than `limit` rows, remaining candidates are ranked
     with difflib.SequenceMatcher against code / first / last / full name /
     email, and anything scoring >= cutoff is appended after exact hits.

Guardrails: queries shorter than 3 chars skip fuzzy (too noisy), and digit
queries are left to the exact digit-normalized SQL match.
"""
from __future__ import annotations

import difflib
import sqlite3

MIN_FUZZY_LEN = 3
DEFAULT_CUTOFF = 0.6
CANDIDATE_POOL = 1000

_SCORED_FIELDS = ("member_code", "first_name", "last_name", "email")


def similarity(a: str, b: str) -> float:
    """Case-insensitive similarity ratio in [0.0, 1.0]."""
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def row_score(query: str, row: sqlite3.Row | dict) -> float:
    """Best similarity of query against any searchable text field of a row."""
    get = row.get if isinstance(row, dict) else row.__getitem__
    try:
        full = f"{get('first_name') or ''} {get('last_name') or ''}"
    except (KeyError, IndexError):
        return 0.0
    candidates = [str(get(f) or "") for f in _SCORED_FIELDS] + [full]
    return max(similarity(query, c) for c in candidates)


def fuzzy_rank(query: str, rows: list,
               *, cutoff: float = DEFAULT_CUTOFF,
               limit: int = 100) -> list[tuple[float, object]]:
    """Return [(score, row)] for rows scoring >= cutoff, best first."""
    scored = [(row_score(query, r), r) for r in rows]
    return sorted(((s, r) for s, r in scored if s >= cutoff),
                  key=lambda t: t[0], reverse=True)[:limit]
