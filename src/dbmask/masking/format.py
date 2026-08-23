"""Format-preserving transformations.

Replacements must keep the *shape* of the original
value: a 6-character password becomes another 6-character string, a digit stays
a digit, a letter stays a letter, and separators (``-``, ``@``, spaces) are kept
in place. These helpers provide that, driven by a seeded RNG so the mapping is
deterministic (consistent) for a given input.
"""
from __future__ import annotations

import hashlib
import random
import string
from typing import Optional


def seeded_rng(value: str, seed: Optional[str]) -> random.Random:
    """Return a deterministic RNG derived from ``value`` and a global ``seed``.

    The same (value, seed) pair always yields the same RNG, so the same input is
    always masked to the same output — across columns, tables and runs.
    """
    digest = hashlib.sha256(f"{seed or ''}:{value}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def random_char_like(ch: str, rng: random.Random) -> str:
    """Return a random character of the same *class* as ``ch``."""
    if ch.isdigit():
        return rng.choice(string.digits)
    if ch.isupper():
        return rng.choice(string.ascii_uppercase)
    if ch.islower():
        return rng.choice(string.ascii_lowercase)
    # Punctuation, whitespace, separators: preserve as-is.
    return ch


def format_preserving_random(value: str, rng: random.Random) -> str:
    """Replace each character with a random one of the same class.

    Examples
    --------
    ``"Ab3-9z"`` -> ``"Qf7-2k"`` (same length, same digit/letter/sep layout).
    """
    return "".join(random_char_like(ch, rng) for ch in value)


def match_length(replacement: str, original: str, rng: random.Random) -> str:
    """Pad or trim ``replacement`` so it matches ``len(original)``.

    Padding uses characters consistent with the replacement's own style.
    """
    if len(replacement) == len(original):
        return replacement
    if len(replacement) > len(original):
        return replacement[: len(original)]
    pad_pool = string.ascii_lowercase
    pad = "".join(rng.choice(pad_pool) for _ in range(len(original) - len(replacement)))
    return replacement + pad


def preserve_case(template: str, replacement: str) -> str:
    """Apply the upper/lower case pattern of ``template`` onto ``replacement``."""
    out = []
    for i, ch in enumerate(replacement):
        if i < len(template) and template[i].isupper():
            out.append(ch.upper())
        else:
            out.append(ch.lower())
    return "".join(out)


def digits_only_random(value: str, rng: random.Random) -> str:
    """Replace only the digits of ``value``; every other character is kept.

    Used for numeric types, where letters must survive verbatim (``1e-05``
    keeps its ``e``) or the result would no longer parse as a number.
    """
    return "".join(
        rng.choice(string.digits) if ch.isdigit() else ch for ch in value
    )


def luhn_check_digit(partial_digits: str) -> int:
    """Return the check digit that makes ``partial_digits + digit`` Luhn-valid.

    ``partial_digits`` is the card number *without* its final (check) digit.
    """
    total = 0
    # Walk right-to-left over the partial number; the digit immediately left
    # of the check digit is doubled, then every second one after that.
    for i, ch in enumerate(reversed(partial_digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - total % 10) % 10


def coerce_stored(original, stored):
    """Give a seed-map string back the Python type of the original value.

    The seed map stores every masked value as text. When the original arrives
    as a typed object (int, float, Decimal, date, datetime, UUID), the stored
    replacement must go back to the database as that type, or drivers on
    stricter engines reject the write. Falls back to the raw string when the
    conversion does not apply.
    """
    import uuid as uuid_mod
    from datetime import date, datetime
    from decimal import Decimal, InvalidOperation

    if original is None or stored is None:
        return stored
    try:
        if isinstance(original, bool):
            return stored
        if isinstance(original, int):
            return int(stored)
        if isinstance(original, float):
            return float(stored)
        if isinstance(original, Decimal):
            return Decimal(stored)
        if isinstance(original, datetime):
            return datetime.fromisoformat(stored)
        if isinstance(original, date):
            return date.fromisoformat(stored)
        if isinstance(original, uuid_mod.UUID):
            return uuid_mod.UUID(stored)
    except (ValueError, TypeError, InvalidOperation):
        return stored
    return stored
