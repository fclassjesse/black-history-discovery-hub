"""Uploaded partner files, served with an access check (replaces the old open StaticFiles mount).

Rule:
- A file that a PUBLISHED record points to (a finding-aid PDF whose record is live) is public:
  publishing it is the partner's decision to share it.
- Everything else (shelf photos, unpublished or rejected uploads) is visible only to signed-in
  members of the institution that uploaded it. Non-members get 404, so file names cannot be probed.
"""
from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Membership, Record
from app.security import current_user

router = APIRouter(tags=["files"])

# names written by partner._save_upload: 8 hex chars, a dash, a sanitised file name
FILE_NAME = re.compile(r"^[0-9a-f]{8}-[A-Za-z0-9._-]{1,120}$")
PUBLIC_CACHE = "public, max-age=3600"
PRIVATE_CACHE = "private, no-store"


async def _is_published(session: AsyncSession, institution_id: uuid.UUID, url: str) -> bool:
    row = await session.execute(
        select(Record.id).where(Record.institution_id == institution_id, Record.digital_url == url, Record.review_status == "published").limit(1)
    )
    return row.scalar_one_or_none() is not None


async def _is_member(request: Request, session: AsyncSession, institution_id: uuid.UUID) -> bool:
    try:
        user = await current_user(request, session)
    except HTTPException:
        return False
    row = await session.execute(select(Membership.id).where(Membership.user_id == user.id, Membership.institution_id == institution_id).limit(1))
    return row.scalar_one_or_none() is not None


@router.get("/api/files/{institution_id}/{name}")
async def get_file(institution_id: uuid.UUID, name: str, request: Request, session: AsyncSession = Depends(get_session)) -> FileResponse:
    if not FILE_NAME.match(name):
        raise HTTPException(404, "Not found")
    root = get_settings().upload_dir.resolve()
    path = (root / str(institution_id) / name).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "Not found")

    url = f"/api/files/{institution_id}/{name}"
    if await _is_published(session, institution_id, url):
        cache = PUBLIC_CACHE
    elif await _is_member(request, session, institution_id):
        cache = PRIVATE_CACHE
    else:
        raise HTTPException(404, "Not found")
    return FileResponse(path, headers={"Cache-Control": cache, "X-Content-Type-Options": "nosniff"})
