from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Institution, Record
from app.services.cards import institution_card, record_card

router = APIRouter(prefix="/api/institutions", tags=["institutions"])


@router.get("")
async def list_institutions(session: AsyncSession = Depends(get_session)) -> dict:
    rows = await session.execute(select(Institution).order_by(Institution.name))
    insts = list(rows.scalars())
    counts = dict(
        (await session.execute(select(Record.institution_id, func.count()).where(Record.review_status == "published").group_by(Record.institution_id))).all()
    )
    return {"institutions": [{**institution_card(i), "published_records": counts.get(i.id, 0)} for i in insts]}


async def _get(session: AsyncSession, key: str) -> Institution:
    stmt = select(Institution)
    try:
        stmt = stmt.where(Institution.id == uuid.UUID(key))
    except ValueError:
        stmt = stmt.where(Institution.slug == key)
    inst = (await session.execute(stmt)).scalar_one_or_none()
    if inst is None:
        raise HTTPException(404, "Institution not found")
    return inst


@router.get("/{key}")
async def get_institution(key: str, session: AsyncSession = Depends(get_session)) -> dict:
    inst = await _get(session, key)
    count = (await session.execute(select(func.count()).select_from(Record).where(Record.institution_id == inst.id, Record.review_status == "published"))).scalar_one()
    return {**institution_card(inst), "published_records": count}


@router.get("/{key}/records")
async def institution_records(key: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), locale: str = Query("en", pattern="^(en|fr)$"), session: AsyncSession = Depends(get_session)) -> dict:
    inst = await _get(session, key)
    base = select(Record).options(selectinload(Record.institution)).where(Record.institution_id == inst.id, Record.review_status == "published")
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = await session.execute(base.order_by(Record.title).offset((page - 1) * page_size).limit(page_size))
    return {"institution": institution_card(inst), "total": total, "page": page, "page_size": page_size, "results": [record_card(r, locale=locale) for r in rows.scalars()]}
