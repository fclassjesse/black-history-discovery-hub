from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Record, RecordChunk
from app.services.cards import linked_map, record_card

router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("/{record_id}")
async def get_record(record_id: uuid.UUID, locale: str = Query("en", pattern="^(en|fr)$"), session: AsyncSession = Depends(get_session)) -> dict:
    r = (await session.execute(select(Record).options(selectinload(Record.institution)).where(Record.id == record_id))).scalar_one_or_none()
    if r is None or r.review_status != "published":
        raise HTTPException(404, "Record not found")
    linked = await linked_map(session, [r])
    card = record_card(r, linked.get(r.id, []), locale=locale)
    chunks = await session.execute(select(RecordChunk).where(RecordChunk.record_id == r.id).order_by(RecordChunk.chunk_index).limit(3))
    card["excerpts"] = [{"page_number": c.page_number, "page_url": c.page_url, "text": c.text[:600]} for c in chunks.scalars()]
    card["raw_metadata"] = r.raw_metadata
    return card
