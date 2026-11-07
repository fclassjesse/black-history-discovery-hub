"""Background worker: `uv run python -m app.worker`. Polls the jobs table every 2 s."""
from __future__ import annotations

import asyncio

from app.services import jobs
from app.services import shelf_jobs  # noqa: F401  (registers handlers)


async def main() -> None:
    print("[worker] polling jobs table (Ctrl-C to stop)")
    while True:
        n = await jobs.poll_once()
        await asyncio.sleep(0.5 if n else 2.0)


if __name__ == "__main__":
    asyncio.run(main())
