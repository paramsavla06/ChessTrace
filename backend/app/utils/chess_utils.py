from __future__ import annotations

import hashlib


def compute_pgn_hash(pgn_text: str) -> str:
    """
    Compute a SHA-256 hash for the raw pgn text.
    Used to detect duplicate games
    """
    
    return hashlib.sha256(pgn_text.encode("utf-8")).hexdigest()
    