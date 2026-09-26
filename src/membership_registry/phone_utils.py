"""Phone helpers: search numbers as digits, display them with dashes.

Rule: a phone like "123-456" must be findable via "123456", "123-456",
or a substring like "34". Storage keeps the user's original text, but
search compares digit-normalized forms on both sides, and display
ensures dashes for readability.
"""
from __future__ import annotations

import re

_NON_DIGIT_RE = re.compile(r"\D")


def digits_of(value: str | None) -> str:
    """Return digits only, e.g. digits_of('+63-912-345-6789') -> '639123456789'."""
    if not value:
        return ""
    return _NON_DIGIT_RE.sub("", str(value))


def format_phone_display(value: str | None) -> str:
    """Format for display only (never for search/storage).

    - Empty/None -> ""
    - Already contains formatting (space, dash, parens, leading +) -> as-is.
    - Pure digits -> grouped with dashes: 6 digits "123456" -> "123-456",
      7 -> "123-4567", 10 -> "123-456-7890", 11 -> "1-234-567-8901",
      other lengths -> chunks of 3-3-...-rest.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if any(c in s for c in ("-", " ", "(", ")", "/")) or s.startswith("+"):
        return s  # already formatted, keep as stored
    if not s.isdigit():
        return s
    n = len(s)
    if n <= 3:
        return s
    if n == 6:
        return f"{s[:3]}-{s[3:]}"
    if n == 7:
        return f"{s[:3]}-{s[3:]}"
    if n == 10:
        return f"{s[:3]}-{s[3:6]}-{s[6:]}"
    if n == 11:
        return f"{s[:1]}-{s[1:4]}-{s[4:7]}-{s[7:]}"
    # generic: 3-3-rest (e.g. 12 digits -> 123-456-789012 works, keeps substrings intact)
    return f"{s[:3]}-{s[3:6]}-{s[6:]}" if n > 6 else f"{s[:3]}-{s[3:]}"


def sqlite_digits_only(value: str | None) -> str:
    """SQLite scalar function wrapper (registered as digits_only)."""
    return digits_of(value)
