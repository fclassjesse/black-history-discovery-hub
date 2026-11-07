from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import guide, institutions, partner, partner_auth, records, search, status, voice
from app.services.http import get_http


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.upload_dir.mkdir(parents=True, exist_ok=True)
    yield
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
for r in (status.router, search.router, records.router, institutions.router, guide.router, voice.router, partner_auth.router, partner.router):
    app.include_router(r)

get_settings().upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/files", StaticFiles(directory=str(get_settings().upload_dir)), name="files")
