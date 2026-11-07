"""Hybrid search: PostgreSQL FTS (websearch syntax, English + French dictionaries) + pgvector kNN, fused with RRF.

Advanced mode is deterministic SQL only (FTS against both dictionaries in one query + filters, no vectors, no alias
expansion, no LLM). Public search reads only review_status='published'.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import aliases
from app.services.embeddings import get_embeddings
from app.services.normalize import question_to_keywords

RRF_K = 60
CANDIDATES = 300
# Full-text dictionaries: records.search_tsv / record_chunks.tsv use 'english'; records.search_tsv_fr / record_chunks.tsv_fr
# use 'french' (migration 0003). The embedding model (bge-small-en) is English-only, so French recall rests on these.
FTS_DICTS: dict[str, tuple[str, str]] = {"english": ("search_tsv", "tsv"), "french": ("search_tsv_fr", "tsv_fr")}
ALL_DICTS = ("english", "french")
# Cosine-distance floor for the semantic leg (bge-small: related items ≈ 0.2–0.35, nonsense queries ≥ 0.38).
VECTOR_MAX_DISTANCE = 0.37
VECTOR_LIMIT = 60


@dataclass
class SearchFilters:
    resource_types: list[str] = field(default_factory=list)
    access_types: list[str] = field(default_factory=list)
    institution_slugs: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    rights_statuses: list[str] = field(default_factory=list)
    verifications: list[str] = field(default_factory=list)
    source_systems: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)  # where the holding institution is (e.g. "Canada")
    people: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)
    communities: list[str] = field(default_factory=list)
    date_from: int | None = None
    date_to: int | None = None
    identifier: str | None = None
    location: str | None = None  # matches institution city/region/country
    has_full_text: bool | None = None

    @classmethod
    def from_params(cls, d: dict[str, Any] | None) -> "SearchFilters":
        """Build from the public query-string names (types, access, institution, lang, rights, verification, source,
        country, people, places, communities, date_from, date_to, identifier, location, full_text)."""
        d = d or {}

        def csv(k: str) -> list[str]:
            v = d.get(k)
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            return [x.strip() for x in str(v or "").split(",") if x.strip()]

        def year(k: str) -> int | None:
            v = str(d.get(k) or "").strip()
            return int(v) if v.isdigit() and 0 <= int(v) <= 2100 else None

        ft = d.get("full_text")
        return cls(
            resource_types=csv("types"), access_types=csv("access"), institution_slugs=csv("institution"), languages=csv("lang"),
            rights_statuses=csv("rights"), verifications=csv("verification"), source_systems=csv("source"), countries=csv("country"),
            people=csv("people"), places=csv("places"), communities=csv("communities"), date_from=year("date_from"), date_to=year("date_to"),
            identifier=(str(d.get("identifier") or "").strip() or None), location=(str(d.get("location") or "").strip() or None),
            has_full_text=(None if ft in (None, "") else str(ft).lower() in ("1", "true", "yes")),
        )

    def sql(self, params: dict[str, Any], alias: str = "r") -> str:
        clauses = [f"{alias}.review_status = 'published'"]
        if self.resource_types:
            params["f_types"] = self.resource_types
            clauses.append(f"{alias}.resource_type = ANY(:f_types)")
        if self.access_types:
            params["f_access"] = self.access_types
            # 'online' matches online|both, 'physical' matches physical|both
            sub = []
            for a in self.access_types:
                if a == "online":
                    sub.append(f"{alias}.access_type IN ('online','both')")
                elif a == "physical":
                    sub.append(f"{alias}.access_type IN ('physical','both')")
                else:
                    sub.append(f"{alias}.access_type = '{a}'" if a in ("both", "unknown") else "FALSE")
            clauses.append("(" + " OR ".join(sub) + ")")
        if self.institution_slugs:
            params["f_inst"] = self.institution_slugs
            clauses.append(f"{alias}.institution_id IN (SELECT id FROM institutions WHERE slug = ANY(:f_inst))")
        if self.languages:
            params["f_lang"] = self.languages
            clauses.append(f"{alias}.language && :f_lang")
        if self.rights_statuses:
            params["f_rights"] = self.rights_statuses
            clauses.append(f"{alias}.rights_status = ANY(:f_rights)")
        if self.verifications:
            params["f_ver"] = self.verifications
            clauses.append(f"{alias}.holding_verification = ANY(:f_ver)")
        if self.source_systems:
            params["f_src"] = self.source_systems
            clauses.append(f"{alias}.source_system = ANY(:f_src)")
        if self.countries:
            params["f_country"] = self.countries
            clauses.append(f"{alias}.institution_id IN (SELECT id FROM institutions WHERE country = ANY(:f_country))")
        for name, values in (("people", self.people), ("places", self.places), ("communities", self.communities)):
            if values:
                params[f"f_{name}"] = values
                clauses.append(f"{alias}.{name} && :f_{name}")  # GIN-indexed array overlap
        if self.date_from is not None and self.date_to is not None and self.date_from > self.date_to:
            self.date_from, self.date_to = self.date_to, self.date_from  # tolerate reversed ranges deterministically
        if self.date_from is not None:
            params["f_from"] = self.date_from
            clauses.append(f"coalesce({alias}.date_end, {alias}.date_start) >= :f_from")
        if self.date_to is not None:
            params["f_to"] = self.date_to
            clauses.append(f"coalesce({alias}.date_start, {alias}.date_end) <= :f_to")
        if self.identifier:
            params["f_ident"] = f"%{self.identifier.strip()}%"
            clauses.append(f"({alias}.identifiers::text ILIKE :f_ident OR {alias}.call_number ILIKE :f_ident OR {alias}.source_record_id ILIKE :f_ident)")
        if self.location:
            params["f_loc"] = f"%{self.location.strip()}%"
            clauses.append(
                f"{alias}.institution_id IN (SELECT id FROM institutions WHERE city ILIKE :f_loc OR region ILIKE :f_loc OR country ILIKE :f_loc OR name ILIKE :f_loc)"
            )
        if self.has_full_text is not None:
            params["f_ft"] = self.has_full_text
            clauses.append(f"{alias}.has_full_text = :f_ft")
        return " AND ".join(clauses)


def _fts_sql(dicts: tuple[str, ...], table_alias: str, which: int) -> tuple[str, str, str]:
    """(FROM-clause tsquery sources, WHERE match expression, rank expression) for the given dictionaries.

    ``which`` picks the record column (0) or the chunk column (1). Several dictionaries are OR-ed and ranked by the
    best of them, which keeps a single deterministic query for Advanced mode.
    """
    sources = ", ".join(f"websearch_to_tsquery('{d}', :q) tq_{d[:2]}" for d in dicts)
    match = " OR ".join(f"{table_alias}.{FTS_DICTS[d][which]} @@ tq_{d[:2]}" for d in dicts)
    ranks = [f"ts_rank_cd({table_alias}.{FTS_DICTS[d][which]}, tq_{d[:2]})" for d in dicts]
    rank = ranks[0] if len(ranks) == 1 else "greatest(" + ", ".join(ranks) + ")"
    return sources, f"({match})", rank


async def _fts_ids(session: AsyncSession, q: str, filters: SearchFilters, limit: int, dicts: tuple[str, ...] = ("english",)) -> list[uuid.UUID]:
    params: dict[str, Any] = {"q": q, "limit": limit}
    where = filters.sql(params)
    sources, match, rank = _fts_sql(dicts, "r", 0)
    rows = await session.execute(
        text(f"SELECT r.id FROM records r, {sources} WHERE {where} AND {match} ORDER BY {rank} DESC, r.date_start DESC NULLS LAST LIMIT :limit"),
        params,
    )
    return [row[0] for row in rows]


async def _chunk_fts_ids(session: AsyncSession, q: str, filters: SearchFilters, limit: int, dicts: tuple[str, ...] = ALL_DICTS) -> list[uuid.UUID]:
    params: dict[str, Any] = {"q": q, "limit": limit}
    where = filters.sql(params)
    sources, match, rank = _fts_sql(dicts, "c", 1)
    rows = await session.execute(
        text(
            f"SELECT r.id, max({rank}) AS rank FROM record_chunks c JOIN records r ON r.id = c.record_id, {sources} "
            f"WHERE {where} AND {match} GROUP BY r.id ORDER BY rank DESC LIMIT :limit"
        ),
        params,
    )
    return [row[0] for row in rows]


def vector_expr(column: str, dim: int) -> str:
    """Must match the HNSW expression index in migration 0002: (embedding::vector(N)) with the model predicate."""
    return f"({column}::vector({int(dim)}))"


async def _vector_ids(session: AsyncSession, vec: list[float], model: str, filters: SearchFilters, limit: int, max_distance: float = VECTOR_MAX_DISTANCE) -> list[uuid.UUID]:
    dim = len(vec)
    params: dict[str, Any] = {"vec": str(vec), "model": model, "limit": limit, "maxd": max_distance}
    where = filters.sql(params)
    emb = vector_expr("r.embedding", dim)
    # HNSW is approximate and the filter may be selective, so take a wider ANN window and apply the distance floor on top.
    rows = await session.execute(
        text(
            f"SELECT id FROM (SELECT r.id, {emb} <=> CAST(:vec AS vector({dim})) AS d FROM records r WHERE {where} AND r.embedding_model = :model "
            f"ORDER BY {emb} <=> CAST(:vec AS vector({dim})) LIMIT :limit) t WHERE d < :maxd ORDER BY d"
        ),
        params,
    )
    return [row[0] for row in rows]


async def count_browse(session: AsyncSession, filters: SearchFilters) -> int:
    params: dict[str, Any] = {}
    where = filters.sql(params)
    return int((await session.execute(text(f"SELECT count(*) FROM records r WHERE {where}"), params)).scalar_one())


async def _browse_ids(session: AsyncSession, filters: SearchFilters, limit: int) -> list[uuid.UUID]:
    params: dict[str, Any] = {"limit": limit}
    where = filters.sql(params)
    rows = await session.execute(text(f"SELECT r.id FROM records r WHERE {where} ORDER BY r.updated_at DESC LIMIT :limit"), params)
    return [row[0] for row in rows]


def rrf(rankings: list[list[uuid.UUID]], weights: list[float] | None = None) -> list[uuid.UUID]:
    scores: dict[uuid.UUID, float] = {}
    weights = weights or [1.0] * len(rankings)
    for ranking, w in zip(rankings, weights, strict=True):
        for rank, rid in enumerate(ranking, start=1):
            scores[rid] = scores.get(rid, 0.0) + w / (RRF_K + rank)
    return [rid for rid, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]


async def search_ids(session: AsyncSession, query: str, filters: SearchFilters, *, mode: str = "natural", limit: int = CANDIDATES) -> list[uuid.UUID]:
    q = (query or "").strip()
    if not q:
        return await _browse_ids(session, filters, limit)
    if mode == "advanced":
        # one SQL query, both dictionaries OR-ed, ranked by the better score: deterministic, no expansion
        return await _fts_ids(session, q, filters, limit, ALL_DICTS)
    kw = question_to_keywords(q)
    variants = aliases.expand(kw)
    rankings: list[list[uuid.UUID]] = []
    weights: list[float] = []
    for i, v in enumerate(variants):
        # one ranking per dictionary so a French query is stemmed the French way and an English one the English way;
        # a record that matches both simply gathers both RRF contributions
        for d in ALL_DICTS:
            rankings.append(await _fts_ids(session, v, filters, limit, (d,)))
            weights.append((1.0 if i == 0 else 0.6) * (1.0 if d == "english" else 0.9))
    rankings.append(await _chunk_fts_ids(session, kw, filters, limit))
    weights.append(0.8)
    try:
        provider = get_embeddings()
        vec = (await provider.embed([kw]))[0]
        rankings.append(await _vector_ids(session, vec, provider.model, filters, VECTOR_LIMIT))
        weights.append(0.9)
    except Exception:  # noqa: BLE001 — vector search is an enhancement; FTS still answers
        pass
    return rrf(rankings, weights)[:limit]


async def chunk_hits(session: AsyncSession, query: str, k: int = 8, filters: SearchFilters | None = None) -> list[dict[str, Any]]:
    """Top passages (FTS ∪ vector) for the guide, restricted to published records that pass the filters."""
    q = question_to_keywords((query or "").strip())
    if not q:
        return []
    filters = filters or SearchFilters()
    params: dict[str, Any] = {"q": q, "k": k}
    where = filters.sql(params)
    found: dict[uuid.UUID, dict[str, Any]] = {}
    sources, match, rank = _fts_sql(ALL_DICTS, "c", 1)
    rows = await session.execute(
        text(
            f"SELECT c.id, c.record_id, c.chunk_index, c.page_number, c.text, c.page_url, c.kind, {rank} AS rank "
            f"FROM record_chunks c JOIN records r ON r.id = c.record_id, {sources} "
            f"WHERE {where} AND {match} ORDER BY rank DESC LIMIT :k"
        ),
        params,
    )
    order: list[list[uuid.UUID]] = [[]]
    for row in rows:
        found[row[0]] = {"chunk_id": row[0], "record_id": row[1], "chunk_index": row[2], "page_number": row[3], "text": row[4], "page_url": row[5], "kind": row[6]}
        order[0].append(row[0])
    try:
        provider = get_embeddings()
        vec = (await provider.embed([q]))[0]
        dim = len(vec)
        emb = vector_expr("c.embedding", dim)
        rows = await session.execute(
            text(
                f"SELECT c.id, c.record_id, c.chunk_index, c.page_number, c.text, c.page_url, c.kind FROM record_chunks c JOIN records r ON r.id = c.record_id "
                f"WHERE {where} AND c.embedding_model = :model "
                f"ORDER BY {emb} <=> CAST(:vec AS vector({dim})) LIMIT :k"
            ),
            {**params, "vec": str(vec), "model": provider.model},
        )
        order.append([])
        for row in rows:
            found.setdefault(row[0], {"chunk_id": row[0], "record_id": row[1], "chunk_index": row[2], "page_number": row[3], "text": row[4], "page_url": row[5], "kind": row[6]})
            order[1].append(row[0])
    except Exception:  # noqa: BLE001
        pass
    return [found[cid] for cid in rrf(order)[:k]]
