"""Cautious de-duplication: same dedupe_key across institutions/sources is LINKED ('also catalogued at'), never merged."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Record
from app.services.normalize import dedupe_key


def dedupe_key_for(title: str | None, creators: list[str] | None, year: int | None) -> str | None:
    return dedupe_key(title, creators, year)


async def linked_records(session: AsyncSession, record: Record) -> list[Record]:
    if not record.dedupe_key:
        return []
    rows = await session.execute(
        select(Record).where(Record.dedupe_key == record.dedupe_key, Record.id != record.id, Record.review_status == "published")
    )
    return list(rows.scalars())


async def existing_keys_for_institution(session: AsyncSession, institution_id: uuid.UUID) -> set[str]:
    rows = await session.execute(select(Record.dedupe_key).where(Record.institution_id == institution_id, Record.dedupe_key.is_not(None)))
    return {k for (k,) in rows if k}
