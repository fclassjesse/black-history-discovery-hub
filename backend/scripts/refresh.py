"""Refresh path (run on a schedule, e.g. weekly cron):
1. re-run every live connector for the seed queries (new records added, changed records updated, counts logged in connector_runs),
2. re-embed records whose embedding is missing or was made with a different model,
3. build description passages for records that still have no chunks.

  uv run python scripts/refresh.py                 # all connectors
  uv run python scripts/refresh.py --source dal_oai --max 40
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text  # noqa: E402

from app.db import session_factory  # noqa: E402
from app.models import Record, RecordChunk  # noqa: E402
from app.services.embeddings import get_embeddings  # noqa: E402
from app.services.passages import description_passages  # noqa: E402
from app.services.repository import embed_record  # noqa: E402
from scripts.seed import run_connectors  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="only this connector")
    ap.add_argument("--max", type=int, default=40, help="records per query per connector")
    ap.add_argument("--no-connectors", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    async with session_factory()() as session:
        if not args.no_connectors:
            summary = await run_connectors(session, args.max, only=args.source)
            for row in summary:
                print(f"  {row['source']:20s} {row['status']:12s} new={row['records']:4d}  {row['detail'][:80]}")
        provider = get_embeddings()
        stale = list((await session.execute(
            select(Record).where((Record.embedding.is_(None)) | (Record.embedding_model.is_distinct_from(provider.model)))
        )).scalars())
        print(f"[refresh] re-embedding {len(stale)} records with {provider.model}")
        for i, r in enumerate(stale, 1):
            await embed_record(session, r)
            if i % 100 == 0:
                await session.commit()
                print(f"  {i}/{len(stale)}", flush=True)
        await session.commit()
        missing = list((await session.execute(text(
            "SELECT r.id FROM records r WHERE length(coalesce(r.description,'')) >= 400 AND NOT EXISTS (SELECT 1 FROM record_chunks c WHERE c.record_id = r.id)"
        ))).scalars())
        added = 0
        for rid in missing:
            r = await session.get(Record, rid)
            if r is None:
                continue
            for c in description_passages(r.description, r.original_url):
                session.add(RecordChunk(record_id=r.id, chunk_index=c.chunk_index, text=c.text, page_url=c.page_url, kind="description"))
                added += 1
            await session.flush()
            await embed_record(session, r)
        await session.commit()
        print(f"[refresh] description passages added: {added}")
    print(f"[refresh] done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
