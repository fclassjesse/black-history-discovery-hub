from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import files, guide, institutions, partner, partner_auth, records, search, status, voice
from app.services import searchlog
from app.services.http import get_http


logger = logging.getLogger(__name__)


async def _warm_models() -> None:
    """Loads the local embedding model and cross-encoder once at startup. Cold, they add ~1.5 s + ~1 s to the first
    search (model load + ONNX session init), which the UI shows as a stalled globe. Failures only cost that delay."""
    s = get_settings()
    try:
        if s.embeddings_provider == "local":
            from app.services.embeddings import get_embeddings

            await get_embeddings().embed(["warm up"])
        if s.reranker == "local":
            from app.services.rerank import get_reranker

            await get_reranker().rerank("warm up", ["warm up"])
    except Exception:  # noqa: BLE001 — warm-up is an optimisation; the first request loads lazily instead
        logger.warning("model warm-up failed; models will load on first request", exc_info=True)


PRUNE_EVERY_SECONDS = 24 * 3600


async def _prune_search_log_daily() -> None:
    """Search-log retention: on startup, then once a day."""
    while True:
        try:
            removed = await searchlog.prune_old()
            if removed:
                logger.info("search_log retention: deleted %d old rows", removed)
        except Exception:  # noqa: BLE001 — retry tomorrow; never take the API down over housekeeping
            logger.warning("search_log retention failed", exc_info=True)
        await asyncio.sleep(PRUNE_EVERY_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.upload_dir.mkdir(parents=True, exist_ok=True)
    warm = asyncio.create_task(_warm_models())  # in the background: startup is not delayed
    prune = asyncio.create_task(_prune_search_log_daily())
    yield
    warm.cancel()
    prune.cancel()
    await get_http().aclose()


app = FastAPI(
    title="Black History Discovery Hub API",
    version="0.1.0",
    description="Evidence-first discovery layer. Partner API: see docs/partner-api.md. All partner routes require a session cookie and institution membership.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (files.router, status.router, search.router, records.router, institutions.router, guide.router, voice.router, partner_auth.router, partner.router):
    app.include_router(r)

# uploaded files are served by routers/files.py with an access check (published finding aids public, the rest members-only)
