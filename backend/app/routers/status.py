from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.searchlog import gaps_summary
from app.services.status import sources_status

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    await session.execute(text("SELECT 1"))
    return {"ok": True}


@router.get("/status/sources")
async def status_sources(session: AsyncSession = Depends(get_session)) -> dict:
    return await sources_status(session)


@router.get("/status/search-log")
async def status_search_log(days: int = 7, session: AsyncSession = Depends(get_session)) -> dict:
    """Search gaps: most-asked queries, zero-result queries, guide abstentions and latency over the last N days."""
    return await gaps_summary(session, days=max(1, min(days, 90)))
