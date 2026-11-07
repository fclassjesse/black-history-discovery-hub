"""Recompute embeddings for every record + chunk with the active EMBEDDINGS_PROVIDER/model.
  uv run python scripts/reindex.py [--only-missing]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import session_factory  # noqa: E402
from app.models import Record  # noqa: E402
from app.services.embeddings import get_embeddings  # noqa: E402
from app.services.repository import embed_record  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-missing", action="store_true")
    args = ap.parse_args()
    provider = get_embeddings()
    print(f"[reindex] provider={provider.name} model={provider.model}")
    async with session_factory()() as session:
        stmt = select(Record)
        if args.only_missing:
            stmt = stmt.where((Record.embedding_model.is_(None)) | (Record.embedding_model != provider.model))
        rows = list((await session.execute(stmt)).scalars())
        for i, r in enumerate(rows, 1):
            await embed_record(session, r)
            if i % 25 == 0:
                await session.commit()
                print(f"  {i}/{len(rows)}")
        await session.commit()
    print(f"[reindex] done: {len(rows)} records")


if __name__ == "__main__":
    asyncio.run(main())
