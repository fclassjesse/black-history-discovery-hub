"""Optional local cross-encoder reranker (fastembed, keyless). Reorders a short candidate list by query relevance.

RERANKER=local (default) | none. Falls back to the input order on any failure, so retrieval never depends on it.
"""
from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from app.config import get_settings

MAX_PAIRS = 40
MAX_CHARS = 500  # per pair; latency is roughly linear in pairs × tokens


class Reranker:
    name = "none"
    model = ""

    async def rerank(self, query: str, texts: list[str]) -> list[float]:
        return [0.0] * len(texts)


class LocalReranker(Reranker):
    name = "local"

    def __init__(self, model: str) -> None:
        self.model = model
        self._m: Any = None

    def _load(self) -> Any:
        if self._m is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._m = TextCrossEncoder(model_name=self.model)
        return self._m

    async def rerank(self, query: str, texts: list[str]) -> list[float]:
        m = await asyncio.to_thread(self._load)
        return [float(s) for s in await asyncio.to_thread(lambda: list(m.rerank(query, texts)))]


@lru_cache
def get_reranker() -> Reranker:
    s = get_settings()
    if s.reranker == "local":
        return LocalReranker(s.reranker_model)
    return Reranker()


async def rerank_items(query: str, items: list[Any], text_of, *, top: int | None = None) -> list[Any]:
    """Returns `items` reordered by cross-encoder score (best first). On any error, the original order."""
    if not items or get_settings().reranker == "none":
        return items
    head, tail = items[:MAX_PAIRS], items[MAX_PAIRS:]
    try:
        scores = await get_reranker().rerank(query, [text_of(i)[:MAX_CHARS] for i in head])
    except Exception:  # noqa: BLE001 — reranking is an enhancement, never a dependency
        return items
    ordered = [i for _, i in sorted(zip(scores, head, strict=True), key=lambda p: p[0], reverse=True)]
    out = ordered + tail
    return out[:top] if top else out
