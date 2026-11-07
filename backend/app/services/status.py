from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import all_adapters
from app.config import get_settings
from app.models import ConnectorRun, Record, RecordChunk
from app.services.llm import provider_info


async def sources_status(session: AsyncSession) -> dict[str, Any]:
    s = get_settings()
    statuses = await asyncio.gather(*(a.status() for a in all_adapters()))
    out = []
    for st in statuses:
        last = (
            await session.execute(select(ConnectorRun).where(ConnectorRun.source_system == st.name).order_by(ConnectorRun.started_at.desc()).limit(1))
        ).scalar_one_or_none()
        count = (await session.execute(select(func.count()).select_from(Record).where(Record.source_system == st.name, Record.review_status == "published"))).scalar_one()
        d = st.model_dump()
        d["published_records"] = count
        d["last_run"] = (
            {"status": last.status, "query": last.query, "fetched": last.fetched, "upserted": last.upserted, "started_at": last.started_at.isoformat(), "error": last.error, "request_url": last.request_url}
            if last else None
        )
        out.append(d)
    partner_count = (await session.execute(select(func.count()).select_from(Record).where(Record.source_system.like("partner:%"), Record.review_status == "published"))).scalar_one()
    chunk_count = (await session.execute(select(func.count()).select_from(RecordChunk))).scalar_one()
    emb = provider_info()
    return {
        "connectors": out,
        "partner_published_records": partner_count,
        "full_text_chunks": chunk_count,
        "ai": {
            "guide": emb,
            "vision": {**emb, "configured": emb["configured"]},
            "embeddings": {"provider": s.embeddings_provider, "model": s.local_embedding_model if s.embeddings_provider == "local" else s.openai_embedding_model},
            "voice": {"browser_speech": True, "server_transcription": bool(s.openai_api_key), "note": "Push-to-talk only; transcript is editable before submission."},
        },
        "map": {"tiles": "https://tiles.openfreemap.org/styles/positron", "attribution": "© OpenFreeMap © OpenMapTiles © OpenStreetMap contributors", "geocoder": "Nominatim (OpenStreetMap), 1 req/s, cached"},
    }
