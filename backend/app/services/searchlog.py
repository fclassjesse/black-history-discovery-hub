"""Search / guide logging and the "search gaps" summary. Stores the query text and counts only — no user data."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session_factory
from app.models import SearchLog


async def log_search(*, kind: str, query: str, mode: str | None, filters: dict[str, Any], result_count: int, took_ms: int, abstained: bool | None = None) -> None:
    """Writes in its own session so a logging failure can never break a request."""
    q = (query or "").strip()[:500]
    if not q:
        return
    try:
        async with session_factory()() as s:
            s.add(SearchLog(kind=kind, query=q, mode=mode, filters={k: v for k, v in filters.items() if v}, result_count=result_count, took_ms=took_ms, abstained=abstained))
            await s.commit()
    except Exception:  # noqa: BLE001
        pass


async def gaps_summary(session: AsyncSession, days: int = 7) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    top = (await session.execute(text(
        "SELECT lower(query) AS q, count(*) AS n, max(result_count) AS best FROM search_log WHERE created_at >= :since AND kind = 'search' "
        "GROUP BY lower(query) ORDER BY n DESC, q LIMIT 15"), {"since": since})).all()
    zero = (await session.execute(text(
        "SELECT lower(query) AS q, count(*) AS n FROM search_log WHERE created_at >= :since AND kind = 'search' AND result_count = 0 "
        "GROUP BY lower(query) ORDER BY n DESC, q LIMIT 15"), {"since": since})).all()
    abst = (await session.execute(text(
        "SELECT lower(query) AS q, count(*) AS n FROM search_log WHERE created_at >= :since AND kind = 'guide' AND abstained IS TRUE "
        "GROUP BY lower(query) ORDER BY n DESC, q LIMIT 15"), {"since": since})).all()
    lat = (await session.execute(text(
        "SELECT kind, count(*), percentile_cont(0.5) WITHIN GROUP (ORDER BY took_ms), percentile_cont(0.95) WITHIN GROUP (ORDER BY took_ms) "
        "FROM search_log WHERE created_at >= :since GROUP BY kind"), {"since": since})).all()
    return {
        "days": days,
        "top_queries": [{"query": r[0], "count": r[1], "best_result_count": r[2]} for r in top],
        "zero_result_queries": [{"query": r[0], "count": r[1]} for r in zero],
        "guide_abstained": [{"query": r[0], "count": r[1]} for r in abst],
        "latency": {r[0]: {"count": r[1], "p50_ms": round(r[2] or 0), "p95_ms": round(r[3] or 0)} for r in lat},
    }
