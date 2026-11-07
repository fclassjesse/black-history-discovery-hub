"""Recompute derived fields for existing records without re-fetching anything:
people / places / communities (entities), work_keys (relationship mapping), description passages (for records with
no OCR pages) and embeddings whose text changed. Idempotent.

  uv run python scripts/backfill_entities.py            # everything
  uv run python scripts/backfill_entities.py --no-embed # skip re-embedding
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.db import session_factory  # noqa: E402
from app.models import Record, RecordChunk  # noqa: E402
from app.services.entities import entities_for  # noqa: E402
from app.services.passages import description_passages  # noqa: E402
from app.services.repository import embed_record  # noqa: E402
from app.services.workkeys import work_keys_for  # noqa: E402

BATCH = 100


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-embed", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    stats = {"records": 0, "with_people": 0, "with_places": 0, "with_communities": 0, "work_keys": 0, "passages_added": 0, "embedded": 0}
    async with session_factory()() as session:
        ids = list((await session.execute(select(Record.id).order_by(Record.created_at))).scalars())
        for start in range(0, len(ids), BATCH):
            batch_ids = ids[start : start + BATCH]
            records = list((await session.execute(select(Record).where(Record.id.in_(batch_ids)))).scalars())
            for r in records:
                ents = entities_for(r.title, r.creators, r.subjects, r.description)
                r.people, r.places, r.communities = ents["people"], ents["places"], ents["communities"]
                r.work_keys = work_keys_for(r.identifiers, r.raw_metadata, r.title, r.creators, r.date_start)
                stats["records"] += 1
                stats["with_people"] += bool(r.people)
                stats["with_places"] += bool(r.places)
                stats["with_communities"] += bool(r.communities)
                stats["work_keys"] += len(r.work_keys)
                has_pages = (await session.execute(select(RecordChunk.id).where(RecordChunk.record_id == r.id, RecordChunk.kind == "page").limit(1))).first() is not None
                r.has_full_text = has_pages
                if not has_pages and not args.no_embed:  # passages need embeddings; --no-embed is an entities-only pass
                    await session.execute(delete(RecordChunk).where(RecordChunk.record_id == r.id, RecordChunk.kind == "description"))
                    passages = description_passages(r.description, r.original_url)
                    for c in passages:
                        session.add(RecordChunk(record_id=r.id, chunk_index=c.chunk_index, page_number=None, text=c.text, page_url=c.page_url, kind="description"))
                    stats["passages_added"] += len(passages)
                await session.flush()
                if not args.no_embed:
                    await embed_record(session, r)
                    stats["embedded"] += 1
            await session.commit()
            print(f"  {min(start + BATCH, len(ids))}/{len(ids)} records · {time.time() - t0:.0f}s", flush=True)
    print("done", stats, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
