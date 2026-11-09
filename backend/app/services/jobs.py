"""Minimal job queue on the `jobs` table. JOBS_INLINE=true runs jobs immediately (dev/tests);
`python -m app.worker` polls the table otherwise."""
from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import session_factory
from app.models import Job

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]
_HANDLERS: dict[str, Handler] = {}


def handler(kind: str):
    def deco(fn: Handler) -> Handler:
        _HANDLERS[kind] = fn
        return fn

    return deco


async def enqueue(session: AsyncSession, kind: str, payload: dict[str, Any]) -> Job:
    job = Job(kind=kind, payload=payload)
    session.add(job)
    await session.flush()
    return job


async def run_job(job_id: uuid.UUID) -> None:
    async with session_factory()() as session:
        job = await session.get(Job, job_id)
        if job is None or job.status not in ("queued", "failed"):
            return
        job.status = "running"
        job.attempts += 1
        job.started_at = datetime.now(timezone.utc)
        await session.commit()
        try:
            fn = _HANDLERS[job.kind]
            await fn(session, job.payload)
            job.status = "done"
            job.error = None
        except Exception:  # noqa: BLE001
            await session.rollback()
            job = await session.get(Job, job_id)
            assert job is not None
            job.status = "failed"
            job.error = traceback.format_exc()[-2000:]
        job.finished_at = datetime.now(timezone.utc)
        await session.commit()


_BACKGROUND: set[asyncio.Task[None]] = set()


async def maybe_run_inline(job: Job) -> None:
    settings = get_settings()
    if not settings.jobs_inline:
        return
    if not settings.jobs_inline_background:
        await run_job(job.id)
        return
    task = asyncio.create_task(run_job(job.id))  # client polls the scan until it leaves queued/processing
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)


async def poll_once() -> int:
    async with session_factory()() as session:
        rows = await session.execute(select(Job.id).where(Job.status == "queued").order_by(Job.created_at).limit(5))
        ids = [r[0] for r in rows]
    for jid in ids:
        await run_job(jid)
    return len(ids)
