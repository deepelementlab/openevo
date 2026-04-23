"""Lightweight deterministic text embeddings (no external ML deps)."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Sequence


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+|\S", text.lower()) or ["empty"]


def text_embedding(text: str, dim: int = 128) -> list[float]:
    """Hash-seeded bag-of-tokens embedding; L2-normalized."""
    vec = [0.0] * dim
    for tok in _tokens(text):
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(dim):
            vec[i] += (h[i % len(h)] - 128) / 128.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)
