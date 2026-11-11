"""Deterministic seeds: SHA-256 of the joined values, never Python's ``hash()``."""

from __future__ import annotations

import hashlib

SEPARATOR = "|"


def seed_hex(*parts: object) -> str:
    """Full SHA-256 hex digest of the parts joined with ``|``."""
    text = SEPARATOR.join(str(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seed_int(*parts: object) -> int:
    """64-bit integer seed taken from the first 8 bytes of :func:`seed_hex`."""
    return int(seed_hex(*parts)[:16], 16)


def grid_label(rows: int, cols: int) -> str:
    return f"{rows}x{cols}"
