"""Deterministic hashing helpers (never use Python's salted built-in hash())."""

from __future__ import annotations

import hashlib
from typing import Any


def stable_uint32(*parts: object) -> int:
    """Stable unsigned 32-bit integer from SHA-256 of joined parts."""
    text = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big", signed=False)


def stable_seed(*parts: Any, modulus: int = 10_000_000) -> int:
    """Non-negative seed for RNG / cache keys."""
    if modulus <= 0:
        raise ValueError("modulus must be positive")
    return stable_uint32(*parts) % modulus


def stable_hex(*parts: Any, n_chars: int = 16) -> str:
    text = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n_chars]


def stable_record_id(*parts: object) -> str:
    """Deterministic record identifier for generated IDs."""
    return f"rec_{stable_hex(*parts, n_chars=16)}"
