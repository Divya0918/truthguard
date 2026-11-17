"""
Embedding service — sentence-transformers with offline fallback.

Uses `sentence-transformers/all-MiniLM-L6-v2` when available.
Falls back to deterministic TF-IDF-style hashing so the app
still runs on machines without GPU / internet access.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Any

import numpy as np

_MODEL: Any = None
_USE_ST = True
_DIM = 384  # MiniLM dimension


def _load_model() -> None:
    global _MODEL, _USE_ST
    if _MODEL is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        _USE_ST = True
    except Exception:
        _USE_ST = False


def _hash_embed(text: str) -> list[float]:
    """Deterministic pseudo-embedding via character n-gram hashing."""
    vec = [0.0] * _DIM
    tokens = re.findall(r"\w+", text.lower())
    for tok in tokens:
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        idx = h % _DIM
        vec[idx] += 1.0
    # L2 normalise
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class EmbeddingService:
    """Async-friendly embedding service."""

    async def encode(self, texts: list[str]) -> list[list[float]]:
        _load_model()
        if _USE_ST and _MODEL is not None:
            import asyncio
            loop = asyncio.get_event_loop()
            vecs = await loop.run_in_executor(
                None,
                lambda: _MODEL.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist(),
            )
            return vecs
        return [_hash_embed(t) for t in texts]

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1e-9
        nb = math.sqrt(sum(x * x for x in b)) or 1e-9
        return dot / (na * nb)


embedding_service = EmbeddingService()
