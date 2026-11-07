"""Embeddings provider switch: local fastembed (default, keyless) | openai | fake (tests)."""
from __future__ import annotations

import asyncio
import hashlib
import math
from functools import lru_cache

from app.config import get_settings

FAKE_DIM = 32


class EmbeddingProvider:
    name: str
    model: str
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class FakeEmbeddings(EmbeddingProvider):
    """Deterministic hashed bag-of-words vectors — enough for tests, never for production."""

    name = "fake"
    model = "fake-hash-32"
    dim = FAKE_DIM

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * FAKE_DIM
            for w in t.lower().split():
                h = int(hashlib.md5(w.encode()).hexdigest(), 16)
                v[h % FAKE_DIM] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


class LocalEmbeddings(EmbeddingProvider):
    name = "local"

    def __init__(self, model: str):
        self.model = model
        self._m = None
        self.dim = 384

    def _load(self):
        if self._m is None:
            from fastembed import TextEmbedding

            self._m = TextEmbedding(model_name=self.model)
        return self._m

    async def embed(self, texts: list[str]) -> list[list[float]]:
        m = await asyncio.to_thread(self._load)
        vecs = await asyncio.to_thread(lambda: list(m.embed(texts, batch_size=32)))
        return [v.tolist() for v in vecs]


class OpenAIEmbeddings(EmbeddingProvider):
    name = "openai"

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.dim = 1536
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


@lru_cache
def get_embeddings() -> EmbeddingProvider:
    s = get_settings()
    if s.embeddings_provider == "fake":
        return FakeEmbeddings()
    if s.embeddings_provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("EMBEDDINGS_PROVIDER=openai but OPENAI_API_KEY is not set")
        return OpenAIEmbeddings(s.openai_embedding_model, s.openai_api_key)
    return LocalEmbeddings(s.local_embedding_model)


def record_embedding_text(title: str, creators: list[str], subjects: list[str], description: str | None, *, places: list[str] | None = None, resource_type: str | None = None) -> str:
    """Text the semantic leg sees. Places and type are appended so "photographs of Africville" lands near image
    records about Africville, not just records whose description happens to use those words."""
    parts = [title]
    if creators:
        parts.append("by " + "; ".join(creators[:3]))
    if subjects:
        parts.append("subjects: " + "; ".join(subjects[:8]))
    if places:
        parts.append("places: " + "; ".join(places[:6]))
    if resource_type and resource_type != "other":
        parts.append("type: " + resource_type.replace("_", " "))
    if description:
        parts.append(description[:800])
    return "\n".join(parts)
