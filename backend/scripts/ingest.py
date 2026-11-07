"""Run one connector for one query and upsert the results.
  uv run python scripts/ingest.py --source loc_sru --query "Black Loyalists" --max 20
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.base import get_adapter  # noqa: E402
from app.db import session_factory  # noqa: E402
from app.models import ConnectorRun  # noqa: E402
from app.services.repository import upsert_record  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--full-text", action="store_true", help="fetch OCR pages where permitted (Internet Archive)")
    args = ap.parse_args()
    adapter = get_adapter(args.source)
    st = await adapter.status()
    print(f"[{adapter.name}] status: {st.state} — {st.detail}")
    async with session_factory()() as session:
        run = ConnectorRun(source_system=adapter.name, query=args.query, status="running")
        session.add(run)
        await session.commit()
        if st.state != "ok":
            run.status, run.error, run.finished_at = st.state, st.detail, datetime.now(timezone.utc)
            await session.commit()
            return
        try:
            raws = await adapter.search(args.query, max_records=args.max)
            run.fetched = len(raws)
            for raw in raws:
                rec = adapter.normalize(raw)
                if args.full_text:
                    rec = await adapter.enrich(rec)
                r, created = await upsert_record(session, rec)
                run.upserted += 1
                print(("  + " if created else "  ~ ") + r.title[:90], "→", r.original_url)
            run.status = "ok"
        except Exception as e:  # noqa: BLE001
            run.status, run.error = "error", f"{type(e).__name__}: {e}"
            print("ERROR", run.error)
        run.finished_at = datetime.now(timezone.utc)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
